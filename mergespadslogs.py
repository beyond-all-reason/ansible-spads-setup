import os
import re
from glob import glob

def extract_host_info(filename):
    """
    Extracts the host region and id from the filename.
    Example: [20241002084523]_[20241003074523]_Host[EU1][001]spads.log -> Host[EU1][001]
    """
    match = re.search(r"Host\[\w+\]\[\d+\]", filename)
    return match.group(0) if match else None

def merge_logs(log_dir='./logs', output_file='merged_spads_logs.log'):
    """
    Merges log files from the given directory into one output file, grouping them by Host[region][id].
    """
    # Dictionary to store logs grouped by Host[region][id]
    log_data = {}

    # Find all log files in the specified directory
    log_files = glob(os.path.join(log_dir, '*_spads.log'))

    for log_file in log_files:
        # Extract host info from the filename
        host_info = extract_host_info(log_file)

        if not host_info:
            print(f"Warning: Could not extract Host info from {log_file}. Skipping this file.")
            continue

        # Open and read each log file line by line
        with open(log_file, 'r') as f:
            for line in f:
                # Ensure that each line starts with a valid timestamp
                if re.match(r'^\d{14} -', line):
                    # Add the log entry to the corresponding host entry in the dictionary
                    if host_info not in log_data:
                        log_data[host_info] = []
                    log_data[host_info].append(line)
                else:
                    print(f"Warning: Line in {log_file} doesn't start with a valid timestamp. Skipping line.")
    
    # Write merged logs to the output file
    
    #reformat stuff
    output_data = []
    for host_info, logs in log_data.items():
        for line in logs:
            output_data.append(line[:14] + ' ' + host_info + line[14:])

    output_data = sorted(output_data)
    with open(output_file, 'w') as out_file:
        for line in output_data:
            out_file.write(line)

    print(f"Merged logs written to {output_file}")

if __name__ == "__main__":
    merge_logs()
