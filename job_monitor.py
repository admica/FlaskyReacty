# File: job_monitor.py
"""
Job monitoring and mergecap management for the PCAP Server
"""
from threading import Thread, Event
import subprocess
import os
import time
import traceback
from typing import List
from core import logger, db, PCAP_PATH
from simpleLogger import SimpleLogger

class JobMonitorThread(Thread):
    """Thread to monitor job status and handle mergecap operations"""
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.stop_event = Event()
        self.name = "JobMonitor"
        self.logger = SimpleLogger('job_monitor')

    def handle_mergecap(self, job_id: int, task_files: list) -> bool:
        """Handle mergecap operation for completed tasks"""
        try:
            if len(task_files) == 0:
                return False

            # If only one file, just move it to final location
            if len(task_files) == 1:
                src_file = task_files[0]
                dst_file = f"{PCAP_PATH}/{job_id}.pcap"
                os.rename(src_file, dst_file)
                self.logger.info(f"Single PCAP file moved for job {job_id}")
                return True

            # Multiple files need mergecap
            output_file = f"{PCAP_PATH}/{job_id}.pcap"
            mergecap_cmd = ["mergecap", "-w", output_file] + task_files

            self.logger.debug(f"Running mergecap command: {' '.join(mergecap_cmd)}")
            process = subprocess.run(
                mergecap_cmd,
                capture_output=True,
                text=True
            )

            if process.returncode != 0:
                self.logger.error(f"Mergecap failed for job {job_id}: {process.stderr}")
                return False

            # Clean up temp files after successful merge
            for temp_file in task_files:
                try:
                    os.remove(temp_file)
                except OSError as e:
                    self.logger.warning(f"Failed to remove temp file {temp_file}: {e}")

            return True

        except Exception as e:
            self.logger.error(f"Error in mergecap for job {job_id}: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def determine_job_status(self, task_statuses: list) -> str:
        """Determine final job status based on task statuses"""
        all_complete = all(status == 'Complete' for status in task_statuses)
        if all_complete:
            return 'Complete'

        all_failed_or_skipped = all(status in ['Failed', 'Skipped'] for status in task_statuses)
        if all_failed_or_skipped:
            return 'Failed'

        return 'Partial Complete'

    def update_job_status(self, job_id: int, status: str, result_path: str = None):
        """Update job status and result path"""
        try:
            if result_path:
                db("""
                    UPDATE jobs
                    SET status = %s,
                        result_path = %s,
                        last_modified = NOW()
                    WHERE id = %s
                """, (status, result_path, job_id))
            else:
                db("""
                    UPDATE jobs
                    SET status = %s,
                        last_modified = NOW()
                    WHERE id = %s
                """, (status, job_id))
        except Exception as e:
            self.logger.error(f"Error updating job {job_id} status: {e}")

    def process_completed_job(self, job_id: int, tasks: list):
        """Process a job whose tasks are all complete"""
        try:
            # Update to Merging status first
            self.update_job_status(job_id, 'Merging')

            # Get list of task files that have PCAP data
            task_files = []
            for task in tasks:
                if task['pcap_size'] and task['temp_path']:
                    if os.path.exists(task['temp_path']):
                        task_files.append(task['temp_path'])

            # Perform mergecap if we have files
            final_status = None
            if task_files:
                if self.handle_mergecap(job_id, task_files):
                    final_status = self.determine_job_status([t['status'] for t in tasks])
                    self.update_job_status(job_id, final_status, f"{PCAP_PATH}/{job_id}.pcap")
                else:
                    final_status = 'Failed'
                    self.update_job_status(job_id, final_status)
            else:
                final_status = self.determine_job_status([t['status'] for t in tasks])
                self.update_job_status(job_id, final_status)

            self.logger.info(f"Job {job_id} processing complete. Final status: {final_status}")

        except Exception as e:
            self.logger.error(f"Error processing completed job {job_id}: {e}")
            self.logger.error(traceback.format_exc())
            self.update_job_status(job_id, 'Failed')

    def run(self):
        """Main thread loop"""
        self.logger.info("Job monitor thread starting")
        check_counter = 0

        while not self.stop_event.is_set():
            try:
                time.sleep(1)
                check_counter += 1

                if check_counter < 15:
                    continue

                check_counter = 0

                # Get all running jobs
                jobs = db("""
                    SELECT id
                    FROM jobs
                    WHERE status = 'Running'
                """)

                for job_row in jobs:
                    job_id = job_row[0]

                    # Get all tasks for this job
                    tasks = db("""
                        SELECT id, status, pcap_size, temp_path
                        FROM tasks
                        WHERE job_id = %s
                    """, (job_id,))

                    if not tasks:
                        self.logger.error(f"No tasks found for job {job_id}")
                        continue

                    # Convert to list of dicts for easier handling
                    task_list = [
                        {
                            'id': t[0],
                            'status': t[1],
                            'pcap_size': t[2],
                            'temp_path': t[3]
                        } for t in tasks
                    ]

                    # Check if all tasks are in a final state
                    all_final = all(
                        t['status'] in ['Complete', 'Failed', 'Skipped']
                        for t in task_list
                    )

                    if all_final:
                        self.process_completed_job(job_id, task_list)

            except Exception as e:
                self.logger.error(f"Error in job monitor loop: {e}")
                self.logger.error(traceback.format_exc())
                time.sleep(10)  # Longer sleep on error

    def stop(self):
        """Stop the monitor thread"""
        self.logger.info("Stopping job monitor thread")
        self.stop_event.set()

# Create global instance
job_monitor_thread = JobMonitorThread()
