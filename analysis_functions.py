#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Server Analysis Functions
PATH: ./analysis_functions.py
"""
from PIL import Image
from scapy.all import *
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import interpolate
from scipy.interpolate import interp1d
import ipaddress
import io
import base64
import numpy as np
from collections import Counter
from datetime import datetime
from simpleLogger import SimpleLogger
logger = SimpleLogger('analysis')

plt.style.use('dark_background')

def analyze_protocol_distribution(file_path, chunk_size=1000000):
    packets = rdpcap(file_path)
    protocol_counts = Counter()
    logger.info(f'packets: {packets}, protocol_counts={protocol_counts}')

    for i in range(0, len(packets), chunk_size):
        chunk = packets[i:i+chunk_size]
        chunk_protocol_counts = Counter(packet.sprintf("%IP.proto%") for packet in chunk)
        protocol_counts.update(chunk_protocol_counts)
    #logger.debug(f'after for range loop 0-{len(packets)}, chunk_size={chunk_size}')

    protocols = list(protocol_counts.keys())
    counts = list(protocol_counts.values())

    plot_data = plot_protocol_distribution(protocols, counts)
    dict_data = {
        'protocol_counts': protocol_counts,
        'total_packets': len(packets)
    }
    logger.debug("PROTOCOL_DISTRIB")
    #logger.debug(dict_data)
    return Image.open(plot_data), dict_data


def analyze_conversation_matrix(file_path, chunk_size=1000000):
    packets = rdpcap(file_path)
    conversations = []
    for i in range(0, len(packets), chunk_size):
        chunk = packets[i:i+chunk_size]
        chunk_conversations = [(packet[IP].src, packet[IP].dst) for packet in chunk if IP in packet]
        conversations.extend(chunk_conversations)

    conversation_counts = Counter(conversations)

    # Sort IP addresses numerically
    all_ips = set(ip for conv in conversations for ip in conv)
    sorted_ips = sorted(all_ips, key=lambda ip: ipaddress.ip_address(ip))

    # Create separate sorted lists for src and dst IPs
    src_ips = sorted(set(src for src, _ in conversations), key=lambda ip: ipaddress.ip_address(ip))
    dst_ips = sorted(set(dst for _, dst in conversations), key=lambda ip: ipaddress.ip_address(ip))

    # Create the matrix
    matrix = [[0] * len(dst_ips) for _ in range(len(src_ips))]

    # Fill the matrix
    for (src, dst), count in conversation_counts.items():
        src_index = src_ips.index(src)
        dst_index = dst_ips.index(dst)
        matrix[src_index][dst_index] = count

    plot_data = plot_conversation_matrix(matrix, src_ips, dst_ips)

    dict_data = {
        'conversations': [list(conv) + [count] for conv, count in conversation_counts.items()],
        'src_ips': src_ips,
        'dst_ips': dst_ips
    }
    logger.debug("CONVERSATION_MATRIX")
    #logger.debug(dict_data)
    return Image.open(plot_data), dict_data


def analyze_bandwidth_usage(file_path, chunk_size=1000000, max_points=100):
    packets = rdpcap(file_path)
    timestamps = []
    packet_sizes = []

    for i in range(0, len(packets), chunk_size):
        chunk = packets[i:i+chunk_size]
        chunk_timestamps = [float(packet.time) for packet in chunk]
        chunk_packet_sizes = [len(packet) for packet in chunk]
        timestamps.extend(chunk_timestamps)
        packet_sizes.extend(chunk_packet_sizes)
    #logger.debug(f'after for range loop 0-{len(packets)}, chunk_size={chunk_size}')

    bandwidth = []
    for i, size in enumerate(packet_sizes[:-1]):
        time_diff = timestamps[i+1] - timestamps[i]
        if time_diff != 0:
            bandwidth.append(size / time_diff)
        else:
            bandwidth.append(0)

    timestamps = [datetime.fromtimestamp(ts) for ts in timestamps[:-1]]

    if len(bandwidth) > max_points:
        logger.debug(f"Reducing the number of bandwidth data points to {max_points}...")

        # Calculate indices to keep
        indices = np.linspace(0, len(bandwidth) - 1, max_points, dtype=int)

        # Select data points
        timestamps = [timestamps[i] for i in indices]
        bandwidth = [bandwidth[i] for i in indices]

    # Sort the data chronologically
    sorted_data = sorted(zip(timestamps, bandwidth), key=lambda x: x[0])
    timestamps, bandwidth = zip(*sorted_data)

    plot_data = plot_bandwidth_usage(timestamps, bandwidth)
    dict_data = { "timestamps": [ts.isoformat() for ts in timestamps], "bandwidth": bandwidth }
    logger.debug("BANDWIDTH_USAGE")
    #logger.debug(dict_data)
    return Image.open(plot_data), dict_data


def analyze_packet_size_distribution(file_path, chunk_size=1000000):
    packets = rdpcap(file_path)
    packet_sizes = []

    for i in range(0, len(packets), chunk_size):
        chunk = packets[i:i+chunk_size]
        chunk_packet_sizes = [len(packet) for packet in chunk]
        packet_sizes.extend(chunk_packet_sizes)
    #logger.debug(f'after for range loop 0-{len(packets)} by chunk_size={chunk_size}')

    packet_size_counts = Counter(packet_sizes)
    plot_data = plot_packet_size_distribution(packet_sizes)
    dict_data = {
        'packet_size_counts': dict(packet_size_counts),
        'total_packets': len(packet_sizes)
    }
    logger.debug("PACKET_SIZE")
    #logger.debug(dict_data)
    return Image.open(plot_data), dict_data


def plot_protocol_distribution(protocols, counts):
    plt.figure(figsize=(8, 4))
    plt.bar(protocols, counts, color='#1f77b4')
    plt.xlabel('Protocol', color='white')
    plt.ylabel('Count', color='white')
    plt.title('Protocol Distribution', color='white')
    plt.xticks(rotation=45, color='white')
    plt.yticks(color='white')
    plt.tight_layout()
    logger.debug("plotting protocols")

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    return buffer


def plot_conversation_matrix(matrix, src_ips, dst_ips):
    plt.figure(figsize=(8, 8))
    plt.imshow(matrix, cmap='viridis', interpolation='nearest')
    plt.xlabel('Source IP', color='white')
    plt.ylabel('Destination IP', color='white')
    plt.title('Conversation Matrix', color='white')
    # Rotate and align the tick labels so they look better
    plt.xticks(range(len(dst_ips)), dst_ips, rotation=90, ha='right', color='white')
    plt.yticks(range(len(src_ips)), src_ips, color='white')
    plt.colorbar(label='Packet Count')
    plt.tight_layout()
    logger.debug("plotting matrix")

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    return buffer


def plot_bandwidth_usage(timestamps, bandwidth):
    plt.figure(figsize=(8, 4))
    plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))

    # Use fill_between for area chart
    plt.fill_between(timestamps, bandwidth, color='#2ca02c', alpha=0.6)

    # Add a line on top of the area for better clarity
    plt.plot(timestamps, bandwidth, color='#2ca02c', linewidth=2)

    plt.xlabel('Time', color='white')
    plt.ylabel('Bandwidth (bytes/second)', color='white')
    plt.title('Bandwidth Usage', color='white')
    plt.xticks(color='white')
    plt.yticks(color='white')

    # Format x-axis to show time
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.gcf().autofmt_xdate()  # Rotate and align the tick labels

    # Set background color to black
    plt.gca().set_facecolor('black')
    plt.gcf().set_facecolor('black')

    plt.tight_layout()

    logger.debug("plotting bandwidth")

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    return buffer


def plot_packet_size_distribution(packet_sizes):
    plt.figure(figsize=(8, 4))
    plt.hist(packet_sizes, bins=50, color='#d62728')
    plt.xlabel('Packet Size (bytes)', color='white')
    plt.ylabel('Frequency', color='white')
    plt.title('Packet Size Distribution', color='white')
    plt.xticks(color='white')
    plt.yticks(color='white')
    plt.tight_layout()
    logger.debug("plotting size")

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    return buffer


if __name__ == '__main__':
    import configparser
    import os, sys
    import shlex

    script = os.path.basename(sys.argv[0])
    if len(sys.argv) != 2:
        print(f"Usage: {script} <job_id>")
        print("Example Usage:")
        print(f" {script} 1289")
        sys.exit(1)

    # Read configuration data
    config = configparser.ConfigParser()
    config.read('config.ini')
    config_sections = config.sections()

    IMG_PATH = config.get('DOWNLOADS', 'IMG_PATH') # image file storage
    PCAP_PATH = config.get('DOWNLOADS', 'PCAP_PATH') # pcap file storage
    job_id = int(sys.argv[1])
    file_path = f"{PCAP_PATH}/{job_id}.pcap"
    print(f"Processing {file_path}")

    logger = SimpleLogger('manual_analysis')

    sample_size = 999999999999  # log a little of the output
    chunks = 10000  # number of packets to process at a time

    plot, dict_data = analyze_protocol_distribution(file_path, chunk_size=chunks)
    fullpath = f"{IMG_PATH}/{job_id}.proto.png"
    plot.save(fullpath)

    cmd = [ 'convert', fullpath, '-strip', '-colors', '64', f'png:{shlex.quote(fullpath)}' ] # ImageMagick
    subprocess.run(cmd, check=True)

    plot, dict_data = analyze_conversation_matrix(file_path, chunk_size=chunks)
    fullpath = f"{IMG_PATH}/{job_id}.matrix.png"
    plot.save(fullpath)

    cmd = [ 'convert', fullpath, '-strip', '-colors', '64', f'png:{shlex.quote(fullpath)}' ] # ImageMagick
    subprocess.run(cmd, check=True)

    plot, dict_data = analyze_bandwidth_usage(file_path, chunk_size=chunks)
    fullpath = f"{IMG_PATH}/{job_id}.usage.png"
    plot.save(fullpath)

    cmd = [ 'convert', fullpath, '-strip', '-colors', '64', f'png:{shlex.quote(fullpath)}' ] # ImageMagick
    subprocess.run(cmd, check=True)

    plot, dict_data = analyze_packet_size_distribution(file_path, chunk_size=chunks)
    fullpath = f"{IMG_PATH}/{job_id}.size.png"
    plot.save(fullpath)

    cmd = [ 'convert', fullpath, '-strip', '-colors', '64', f'png:{shlex.quote(fullpath)}' ] # ImageMagick
    subprocess.run(cmd, check=True)

    from time import sleep
    sleep(1) # Allow logger messages to get sent before quitting
