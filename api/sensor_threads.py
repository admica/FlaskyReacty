"""
Sensor thread management for the PCAP Server API
"""
from threading import Thread, Lock
from queue import Queue, Empty as QueueEmpty
import paramiko
import os
import time
import traceback
from typing import Dict
from datetime import datetime, timedelta

from core import logger, config, STATUS, RESULTS
from simpleLogger import SimpleLogger

# Initialize queues and locks
sensor_queues: Dict[str, Queue] = {}
sensor_threads: Dict[str, Thread] = {}
xlogger: Dict[str, SimpleLogger] = {}
analysis_queue = Queue()
request_count = 0
request_count_lock = Lock()

# Get paths from config
try:
    PCAP_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        config.get('DOWNLOADS', 'pcap_path')
    ))
    REMOTE_PATH = config.get('DOWNLOADS', 'remote_path')
    SSH_PUBKEY = os.path.abspath(config.get('SSH', 'pubkey'))
    SSH_TOUT = int(config.get('SSH', 'timeout'))
    SSH_MAX = int(config.get('SSH', 'runtime'))
    ANALYSIS_MAX_FILESIZE = int(config.get('ANALYSIS', 'max_filesize'))
    EVENT_START_BEFORE = int(config.get('EVENT', 'event_start_before'))
    EVENT_END_AFTER = int(config.get('EVENT', 'event_end_after'))

    # Ensure directories exist
    os.makedirs(PCAP_PATH, exist_ok=True)

except (configparser.Error, ValueError, OSError) as e:
    logger.error(f"Configuration error: {e}")
    raise SystemExit("Failed to load critical configuration values")

def sensor_thread(sensor: str):
    """Thread function to handle sensor jobs"""
    xlogger[sensor] = SimpleLogger(f'sensor_{sensor}')

    # Regular sensor lookup from database
    from core import db
    rows = db("SELECT name, fqdn, status, last_update FROM sensors WHERE name = %s", (sensor,))
    if not rows:
        xlogger[sensor].error(f'No sensor info found for {sensor}')
        return
    sensor_info = rows[0]

    sensor_name, sensor_fqdn, status, last_update = sensor_info
    xlogger[sensor].info(f'New Sensor: name={sensor_name}, fqdn={sensor_fqdn}, status={status}')

    if sensor_info:
        while True:
            try:
                queue = sensor_queues[sensor_name]

                try:
                    job = queue.get(timeout=15)
                except QueueEmpty:
                    continue

                if job is None:
                    xlogger[sensor].warning(f'Received stop signal for sensor: {sensor_name}')
                    break

                job_id, start_epoch, end_epoch, request_type, src_ip, dst_ip = job
                xlogger[sensor].info(f'Work: job_id={job_id}, sensor={sensor_name}, start_epoch={start_epoch}, end_epoch={end_epoch}, request_type={request_type}, src_ip={src_ip}, dst_ip={dst_ip}')

                try:
                    # Update job status to "Running"
                    db("UPDATE jobs SET status=%s, started=date_trunc('second', NOW()) WHERE id=%s",
                       (STATUS['Running'], job_id))
                    xlogger[sensor].info(f'job_id={job_id} Running')

                    # Perform the SSH command
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                    ssh.connect(sensor_fqdn, key_filename=SSH_PUBKEY, timeout=SSH_TOUT, auth_timeout=SSH_TOUT)

                    cmd = f"/opt/autopcap_client/latest/run_job.py {job_id} {start_epoch} {end_epoch} {request_type} {src_ip} {dst_ip}"
                    xlogger[sensor].debug(f'ssh cmd={cmd}')
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=SSH_MAX)
                    exit_status = stdout.channel.recv_exit_status()

                    xlogger[sensor].debug(f'SSH exit_status: {exit_status}')
                    stdout_output = stdout.read().decode('utf-8')
                    stderr_output = stderr.read().decode('utf-8')
                    xlogger[sensor].debug(f'SSH stdout: {stdout_output}')
                    xlogger[sensor].debug(f'SSH stderr: {stderr_output}')

                    job_status = db("SELECT status FROM jobs WHERE id = %s", (job_id,))
                    if not job_status or job_status[0][0] == 'Cancelled':
                        logger.info(f"Job {job_id} was cancelled while running - skipping file retrieval")

                    else:  # job has not been cancelled
                        # Update job status to "Retrieving"
                        db("UPDATE jobs SET status=%s WHERE id=%s",
                           (STATUS['Retrieving'], job_id))
                        xlogger[sensor].info(f'job_id={job_id} Retrieving')

                        # Fetch generated pcap file from sensor
                        remote_file_path = f"{REMOTE_PATH}/{job_id}/{job_id}.pcap"
                        local_file_path = f"{PCAP_PATH}/{job_id}.pcap"

                        try:
                            sftp = ssh.open_sftp()
                            sftp.get(remote_file_path, local_file_path)
                            sftp.close()
                            ssh.close()
                        except IOError:
                            pass
                        except Exception as e:
                            logger.debug(f'Unexpected Error in {sensor} thread: {e}')

                        # Check if the file was successfully retrieved
                        if os.path.exists(local_file_path):
                            file_size = os.path.getsize(local_file_path)
                            if file_size < 105:  # pcap header only
                                result = RESULTS['No-data']
                                filename = None
                                analysis = None
                            else:
                                if file_size < 1000000:  # Less than 1MB
                                    result = f"{file_size / 1000:.2f}K"
                                elif file_size < 1000000000:  # Less than 1GB
                                    result = f"{file_size / 1000000:.2f}M"
                                else:
                                    result = f"{file_size / 1000000000:.2f}G"
                                filename = f"{job_id}.pcap"

                                # Don't analyze huge files
                                if file_size < ANALYSIS_MAX_FILESIZE:
                                    analysis = "Queued"
                                else:
                                    analysis = "Manual"
                        else:
                            result = RESULTS['No-data']
                            filename = None
                            analysis = None

                        # Close out the job
                        db("UPDATE jobs SET result=%s, filename=%s, status=%s, completed=date_trunc('second', NOW()), analysis=%s WHERE id=%s",
                           (result, filename, STATUS['Complete'], analysis, job_id))
                        xlogger[sensor].info(f'Work: job_id={job_id} Complete.')

                        if file_size < ANALYSIS_MAX_FILESIZE:
                            analysis_queue.put([job_id, local_file_path])

                except Exception as e:
                    xlogger[sensor].error(f'Exception in job processing: {e}')
                    xlogger[sensor].error(traceback.format_exc())
                    # Update job status to error or incomplete
                    db("UPDATE jobs SET status=%s, completed=date_trunc('second', NOW()) WHERE id=%s",
                       (STATUS['Incomplete'], job_id))

                finally:
                    queue.task_done()

            except Exception as e:
                xlogger[sensor].error(f'Exception in sensor thread loop: {e}')
                xlogger[sensor].error(traceback.format_exc())
                time.sleep(3)

    xlogger[sensor].info(f'Sensor thread for {sensor} is exiting')
