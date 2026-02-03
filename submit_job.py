import os
import subprocess
import argparse
import sys

def submit_to_deadline(args):
    # Paths
    current_dir = os.getcwd()
    
    # 2. Prepare Job Info
    # Auto-generate comment if not provided or if it's one of the generic defaults
    comment = args.comment
    generic_defaults = ["Submitted via Python CLI", "Submitted via GUI"]
    if not comment or comment in generic_defaults:
        mode_str = "Undistort" if args.undistort else "Distort"
        json_name = os.path.basename(args.json_path)
        comment = f"{mode_str} | JSON: {json_name}"

    job_info_file = os.path.join(current_dir, "deadline_job_info.job")
    with open(job_info_file, 'w') as f:
        f.write("Plugin=OpenCVDistortion\n")
        f.write(f"Name={args.job_name}\n")
        f.write(f"Comment={comment}\n")
        f.write(f"Frames={args.frames}\n")
        f.write(f"ChunkSize={args.chunk_size}\n")
        
        # Priority and Pool options could be added here
        if args.priority:
            f.write(f"Priority={args.priority}\n")

    # 3. Prepare Plugin Info (This overrides .param defaults)
    plugin_info_file = os.path.join(current_dir, "deadline_plugin_info.job")
    with open(plugin_info_file, 'w') as f:
        # ScriptPath is now internal to the plugin, no need to send it.
        f.write(f"JsonPath={os.path.abspath(args.json_path)}\n")
        f.write(f"InputFile={args.input_pattern}\n")
        f.write(f"OutputDir={os.path.abspath(args.output_dir)}\n")
        f.write(f"Undistort={'true' if args.undistort else 'false'}\n")

    print(f"Job Info created at: {job_info_file}")
    print(f"Plugin Info created at: {plugin_info_file}")
    
    # 4. Resolve Deadline Command
    if hasattr(args, 'deadline_command') and args.deadline_command:
        deadline_cmd = args.deadline_command
    else:
        deadline_cmd = get_deadline_command()

    if not deadline_cmd:
        print("Error: Could not find 'deadlinecommand'.")
        print("Please ensure Deadline Client is installed or set DEADLINE_PATH environment variable.")
        return

    # 5. Submit via deadlinecommand
    print(f"Submitting to Deadline using: {deadline_cmd}")
    cmd = [deadline_cmd, job_info_file, plugin_info_file]
    
    try:
        # On Windows, shell=True is sometimes needed for PATH resolution, but try without first
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Error/Warning from Deadline:")
            print(result.stderr)
    except Exception as e:
        print(f"Error executing deadlinecommand: {e}")

def get_deadline_command():
    # 1. Check PATH
    import shutil
    cmd = shutil.which("deadlinecommand")
    if cmd:
        return cmd
    
    # 2. Check DEADLINE_PATH environment variable
    deadline_path = os.environ.get("DEADLINE_PATH")
    if deadline_path:
        # DEADLINE_PATH points to the bin folder
        cmd = os.path.join(deadline_path, "deadlinecommand.exe" if os.name == 'nt' else "deadlinecommand")
        if os.path.exists(cmd):
            return cmd

    # 3. Check Default Windows Path
    if os.name == 'nt':
        default_path = r"C:\Program Files\Thinkbox\Deadline10\bin\deadlinecommand.exe"
        if os.path.exists(default_path):
            return default_path
            
    # 4. Check Default Linux/Mac Path
    else:
        default_path = "/opt/Thinkbox/Deadline10/bin/deadlinecommand"
        if os.path.exists(default_path):
            return default_path

    return None

def main():
    parser = argparse.ArgumentParser(description="Submit OpenCV Distortion job to Deadline.")
    
    # Essential Args (MANDATORY: These are written to Plugin Info and cannot be changed in Monitor)
    parser.add_argument("--input", dest="input_pattern", required=True, help="[REQUIRED] Input file pattern (e.g. C:/shot_01.####.exr). This path is fixed in the job.")
    parser.add_argument("--output", dest="output_dir", required=True, help="[REQUIRED] Output directory. This path is fixed in the job.")
    parser.add_argument("--json", dest="json_path", required=True, help="[REQUIRED] Path to transforms.json. This path is fixed in the job.")
    parser.add_argument("--frames", required=True, help="[REQUIRED] Frame range (e.g. 1-100).")
    
    # Python / Env Args
    # parser.add_argument("--script", ...) # Removed
    
    # Options
    parser.add_argument("--distort", dest="undistort", action="store_false", help="Enable Distort mode (Reverse). If not set, defaults to Undistort (Restore). This mode is fixed in the job.")
    parser.add_argument("--chunk-size", default=1, help="Number of frames per task")
    parser.add_argument("--job-name", default="OpenCV Distortion Task", help="Name of the job in Deadline")
    parser.add_argument("--comment", default="Submitted via Python CLI", help="Comment")
    parser.add_argument("--priority", help="Job Priority (0-100)")

    # Default to Undistort=True
    parser.set_defaults(undistort=True)

    args = parser.parse_args()
    
    submit_to_deadline(args)

if __name__ == "__main__":
    main()
