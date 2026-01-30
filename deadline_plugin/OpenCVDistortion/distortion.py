import json
import cv2
import numpy as np
import os
import argparse
import sys
import re

def parse_args():
    parser = argparse.ArgumentParser(description="Process a sequence of images (undistort/distort) based on camera calibration JSON.")
    parser.add_argument("--json_path", type=str, required=True, help="Path to the .json file (e.g., transforms.json).")
    parser.add_argument("--input_pattern", type=str, required=True, help="Input image file pattern (e.g., path/to/image.####.exr).")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save output images.")
    parser.add_argument("--start_frame", type=int, required=True, help="Start frame number.")
    parser.add_argument("--end_frame", type=int, required=True, help="End frame number.")
    parser.add_argument("--undistort", action="store_true", help="Undistort images (restore). Default is to apply distortion (reverse).")
    return parser.parse_args()

def resolve_filename(pattern, frame):
    # Try to find hash-style padding (e.g., ####, ######)
    hash_match = re.search(r'(#+)', pattern)
    if hash_match:
        padding_str = hash_match.group(1)
        padding_len = len(padding_str)
        format_str = "{:0" + str(padding_len) + "d}"
        return pattern.replace(padding_str, format_str.format(frame))
    
    # Try to find printf-style padding (e.g., %04d, %06d)
    elif "%0" in pattern:
        try:
            # Basic printf replacement
            return pattern % frame
        except:
            pass
    
    # If no pattern, return as is (might be single file)
    return pattern

def main():
    args = parse_args()
    
    # 1. Load JSON Data
    if not os.path.exists(args.json_path):
        print(f"Error: JSON file not found at {args.json_path}")
        sys.exit(1)

    print(f"Loading calibration data from {args.json_path}...")
    with open(args.json_path, 'r') as f:
        data = json.load(f)

    # 2. Extract Camera Parameters
    try:
        fl_x = data['fl_x']
        fl_y = data['fl_y']
        cx = data['cx']
        cy = data['cy']
        w = int(data['w'])
        h = int(data['h'])
        
        # Distortion coefficients
        k1 = data.get('k1', 0)
        k2 = data.get('k2', 0)
        k3 = data.get('k3', 0)
        k4 = data.get('k4', 0)
        p1 = data.get('p1', 0)
        p2 = data.get('p2', 0)
        
        is_fisheye = data.get('is_fisheye', False)
        
    except KeyError as e:
        print(f"Error: Missing critical key in JSON data: {e}")
        sys.exit(1)

    # 3. Construct Matrices
    # Camera Matrix (K)
    K = np.array([[fl_x, 0, cx],
                  [0, fl_y, cy],
                  [0, 0, 1]], dtype=np.float32)

    # Distortion Coefficients (D)
    D = np.array([k1, k2, p1, p2, k3, k4, 0, 0], dtype=np.float32)

    # Hardcoded alpha to keep all pixels
    alpha = 1.0

    print(f"  Resolution: {w}x{h}")
    print(f"  Camera Matrix (K):\n{K}")
    print(f"  Distortion Coeffs (D):\n{D}")
    print(f"  Model: {'Fisheye' if is_fisheye else 'Perspective'}")
    print(f"  Mode: {'Restore (Undistorting)' if args.undistort else 'Reverse (Distorting)'}")

    # 4. Pre-calculate Maps
    print("Pre-calculating remapping maps...")
    
    if not args.undistort:
        # Reverse Mode (Default): Create Distorted Image from Linear Image
        # We need a map: Dest(Distorted) -> Src(Linear)
        
        # 1. Create grid for Dest (Distorted)
        grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
        # Shape (N, 1, 2)
        pts = np.stack([grid_x, grid_y], axis=-1).reshape(-1, 1, 2).astype(np.float32)
        
        # 2. Map Distorted Points -> Linear Points
        if is_fisheye:
            D_fish = D[:4]
            # Estimate the linear camera matrix used in the undistorted input
            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D_fish, (w, h), np.eye(3), balance=alpha
            )
            # undistortPoints: Distorted -> Linear
            pts_u = cv2.fisheye.undistortPoints(pts, K, D_fish, np.eye(3), new_K)
        else:
            # Standard Perspective
            new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), alpha, (w, h))
            # undistortPoints: Distorted -> Linear
            pts_u = cv2.undistortPoints(pts, K, D, None, new_K)
            
        map_coords = pts_u.reshape(h, w, 2)
        map1, map2 = cv2.convertMaps(map_coords[..., 0], map_coords[..., 1], cv2.CV_16SC2, nninterpolation=False)
        
    else:
        # Normal Mode (Undistort): Create Linear Image from Distorted Image
        # We need a map: Dest(Linear) -> Src(Distorted)
        
        if is_fisheye:
            D_fish = D[:4]
            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D_fish, (w, h), np.eye(3), balance=alpha
            )
            map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                K, D_fish, np.eye(3), new_K, (w, h), cv2.CV_16SC2
            )
        else:
            new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), alpha, (w, h))
            map1, map2 = cv2.initUndistortRectifyMap(
                K, D, None, new_K, (w, h), cv2.CV_16SC2
            )

    # Ensure output directory exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # 5. Process Sequence
    print(f"Processing frames {args.start_frame} to {args.end_frame}...")
    
    for frame in range(args.start_frame, args.end_frame + 1):
        input_path = resolve_filename(args.input_pattern, frame)
        
        if not os.path.exists(input_path):
            print(f"Error: Input image not found at {input_path}")
            # If a frame is missing, we might want to fail the whole chunk or skip. 
            # In a render farm context, skipping silently can be bad. 
            # Printing "Error:" allows Deadline to catch it via regex if configured.
            continue

        # Determine output filename
        filename = os.path.basename(input_path)
        output_path = os.path.join(args.output_dir, filename)

        # Determine read flags automatically
        read_flags = cv2.IMREAD_COLOR
        if input_path.lower().endswith('.exr'):
            read_flags = cv2.IMREAD_UNCHANGED

        print(f"Frame {frame}: {input_path} -> {output_path}")
        img = cv2.imread(input_path, read_flags)
        
        if img is None:
            print(f"Error: Could not read image: {input_path}")
            continue

        # Perform Remapping
        processed_img = cv2.remap(
            img, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
        )

        # Save result
        save_params = []
        if output_path.lower().endswith('.exr'):
            # Attempt to match the output EXR type to the processing data type
            if processed_img.dtype == np.float32:
                save_params = [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_FLOAT]
            elif processed_img.dtype == np.float16:
                save_params = [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_HALF]

        cv2.imwrite(output_path, processed_img, save_params)
        
    print("Done.")

if __name__ == "__main__":
    main()
