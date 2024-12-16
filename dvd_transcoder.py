#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BAVC DVD Transcoder
# Version History
#   2.0.0-rc8 - 20241216
#       added H.265 format, options to choose CRF to account for space, use of ffprobe to determine original res to output at the same resolution
#       also added option to supply separate ffprobe binary for standalone.
#   2.0.0-rc7 - 20241216
#       detects if ffmpeg is in path
#   2.0.0-rc5 & 6 - 20241216
#       debugging output
#   2.0.0-rc4 - 20241214
#       fixed issue with v210 codec, added support for relative paths (redefining them to their abspath), added overwrite and binary options.
#   2.0.0-rc3 - 20241212
#       additional fixes for Windows support
#   2.0.0-rc2 - 20241212
#       additional Windows support added
#   2.0.0-rc1 - 20241211
#       set to be system agnostic (Linux and Mac currently, Windows incoming). Improved recursive and multi-file processing
#   1.0.0 - 20220907
#       improved error handling, removed old python2 code, removed unused imports. Prime Time!
#   0.2.0 - 20220906
#       Combined Bash Cat and FFmpeg Cat into a single script.
# TODO
# - 

import os
import sys
import glob
import subprocess
import argparse
import platform
import time

__version__ = "2.0.0-rc8"


def main():

    if platform.system() == "Linux":
        system = "Linux"
        mount_cmd = "mount"
        unmount_cmd = "umount"
        mount_pts = "/mnt/"
        ffmpeg_path = subprocess.run(
            ["which", "ffmpeg"], capture_output=True, text=True
        )
        ffmpeg_command = f"{(ffmpeg_path.stdout).rstrip()}"
        ffprobe_path = subprocess.run(
            ["which", "ffprobe"], capture_output=True, text=True
        )
        ffprobe_command = f"{(ffprobe_path.stdout).rstrip()}"
    elif platform.system() == "Darwin":
        system = "Mac"
        mount_cmd = "hdiutil attach"
        unmount_cmd = "hdiutil detach"
        mount_pts = "/Volumes/"
        ffmpeg_path = subprocess.run(
            ["which", "ffmpeg"], capture_output=True, text=True
        )
        ffmpeg_command = f"{(ffmpeg_path.stdout).rstrip()}"
        ffprobe_path = subprocess.run(
            ["which", "ffprobe"], capture_output=True, text=True
        )
        ffprobe_command = f"{(ffprobe_path.stdout).rstrip()}"        
    elif platform.system() == "Windows":
        system = "Windows"
        mount_cmd = "Mount-DiskImage -PassThru"
        unmount_cmd = "Dismount-DiskImage -ImagePath"
        mount_pts = None
        ffmpeg_path = subprocess.run(
            ["where", "ffmpeg"], capture_output=True, text=True
        ).stdout.split('\n')[0]
        ffmpeg_command = ffmpeg_path
        ffprobe_path = subprocess.run(
            ["where", "ffprobe"], capture_output=True, text=True
        ).stdout.split('\n')[0]
        ffprobe_command = ffprobe_path        
    parser = argparse.ArgumentParser(
        description=f"dvd_transcoder version {__version__}: Creates a concatenated video file from an DVD-Video ISO"
    )
    parser.add_argument(
        "-b",
        "--binary",
        dest="binary",
        help="path to the ffmpeg binary if using a standalone",
    )
    parser.add_argument(
        "-c",
        "--crf",
        dest="crf",
        help="change the Constant Rate Factor, default is 18. Lower number, higher bitrate, larger size.",
        type=int,
        default=20,
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        help="the path to the input directory or files",
        required=True,
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="format",
        help="The output format (defaults to H.264. Pick from v210, ProRes, H.264, H.265 FFv1)",
        default="H.264",
    )
    parser.add_argument(
        "-m",
        "--mode",
        dest="mode",
        type=int,
        help="Selects concatenation mode. 1 = Simple Bash Cat, 2 = FFmpeg Cat",
        default=3,
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="the output folder path (optional, defaults to the same as the input)",
    )
    parser.add_argument(
        "-p",
        "--probe",
        dest="probe",
        help="path to the ffprobe binary if using a standalone",
    )
    parser.add_argument(
        "-r",
        "--recurse",
        dest="recurse",
        help="if the input path is a directory, recursively search for all ISO's",
        action="store_true",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="run in verbose mode (including ffmpeg info)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        dest="overwrite",
        action="store_true",
        default=False,
        help="allow overwrite of existing files, adds -y to ffmpeg command",
    )
    args = parser.parse_args()

    if args.binary:
        ffmpeg_command = args.binary
    if ffmpeg_path == '' and not args.binary:
        print("[!] ffmpeg not found in path! If you are using a standalone binary, use the '-b' argument.")
        sys.exit(1)
    if ffprobe_path == '' and not args.probe:
        print("[!] ffprobe not found in path! It is not required, but can detect the resolution of the source video and assist in transcoding to the same resolution.")
        pass
    verbose = args.verbose
    mode = args.mode
    modes = {
        1: f"{bcolors.OKGREEN}[+] Running in Simple Bash Cat mode{bcolors.ENDC}",
        2: f"{bcolors.OKGREEN}[+] Running in FFmpeg Cat mode{bcolors.ENDC}",
        3: f"{bcolors.OKGREEN}[+] Running in Python read/write bytes mode{bcolors.ENDC}",
        }
    if mode not in modes:
        print(f"{bcolors.FAIL}[!] Please select a valid mode (1, 2 or 3)!{bcolors.ENDC}")
        sys.exit(1)
    if system == 'Windows' and mode == 1:
        print(f"{bcolors.WARNING}Simple Bash Cat mode is not available in Windows. Defaulting to Python read/write bytes mode (3){bcolors.ENDC}")
        mode = 3
    print(modes[mode])
    formats = {
        "ProRes": (" -c:v prores -profile:v 3 -c:a pcm_s24le -ar 48000 ", ".mov"),
        "v210": (" -movflags write_colr+faststart -color_primaries smpte170m -color_trc bt709 -colorspace smpte170m -color_range mpeg -vf setfield=bff,setdar=4/3 -c:v v210 -c:a pcm_s24le -ar 48000 ", ".mov"),
        "H.264": (f" -c:v libx264 -pix_fmt yuv420p -movflags faststart -b:v 3500000 -b:a 160000 -ar 48000 -s 640x480 -vf yadif -crf {args.crf} ", ".mp4"),
        "H.265": (f" -c:v libx265 -pix_fmt yuv420p -movflags faststart -b:v 3500000 -b:a 160000 -ar 48000 -s 640x480 -vf yadif -crf {args.crf} ", ".mp4"),
        "FFv1": (" -map 0 -dn -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slicecrc 1 -slices 24 -field_order bb -color_primaries smpte170m -color_trc bt709 -colorspace smpte170m -c:a copy ", ".mkv"),
        }
    if args.format not in formats:
        print("Please choose a valid output format from: v210, ProRes, H.264, H.265, FFv1")
        sys.exit(1)
    else:
        output_format = args.format
        transcode_string, output_ext = formats[output_format]
    overwrite = args.overwrite
    if overwrite:
        transcode_string += " -y "
    else:
        transcode_string += " -n "
    if not args.output:
        if os.path.isdir(args.input):
            if args.input[-1] != os.sep:
                output_path = f"{args.input}{os.sep}"
            else:
                output_path = args.input
        else:
            if args.input[-1] != os.sep:
                output_path = f"{os.path.dirname(args.input)}{os.sep}"
            else:
                output_path = f"{os.path.dirname(args.input)}"
    else:
        if args.output[-1] != os.sep:
            output_path = f"{args.output}{os.sep}"
        else:
            output_path = args.output
    if verbose:
        print("[+] Running in Verbose Mode")
    else:
        ffmpeg_command += " -hide_banner -loglevel panic "

    all_args = vars(args)

    process_files = []
    if os.path.isdir(args.input):
        if args.recurse:
            dir_contents = dir_recurse(args.input)
        else:
            dir_contents = dir_recurse(args.input, recursive=False)
        for file in dir_contents:
            if os.path.splitext(file)[1].lower() == ".iso":
                process_files.append(os.path.abspath(file))
    else:
        process_files.append(os.path.abspath(args.input))

    process_files = sorted(process_files)
    total_files = len(process_files)
    left_to_process = process_files[:]
    for iso in process_files:
        # This part mounts the iso
        print(f"[-] Mounting ISO {iso}")
        if system == "Windows":
            drive_letter = mount_Win_Image(iso, mount_cmd)
            mount_point = f"{drive_letter}:\\"
        else:
            mount_point = mount_Image(iso, mount_pts, mount_cmd)
        print(f"[+] ISO mounted at {mount_point}")

        vob_path = f"{output_path}{os.path.basename(iso)}.VOBS"
        # This part processes the vobs
        try:
            # Move each vob over as a separate file, adding each vob to a list to be concatenated
            if mode == 1:
                print(f"[-] Moving VOBs to {vob_path} and concatenating")
                if cat_move_VOBS_to_local(
                    iso, mount_point, output_path
                ):
                    print(f"[+] Finished moving and concatenating VOBs in {vob_path}")
                    # Transcode vobs into the target format
                    print(f"[-] Transcoding VOBs in {vob_path} to {output_format}")
                    errors = concat_transcode_VOBS(
                        iso, transcode_string, output_ext, ffmpeg_command, ffprobe_command, output_path, verbose
                    )
                    if not errors:
                        print(f"[+] Finished transcoding VOBs to {output_format}")
                        left_to_process.remove(iso)
                    else:
                        print(f"[!] Encountered an error processing {iso}")
                else:
                    print("[!] No VOBs found.")
            elif mode == 2:
                print(
                    f"[-] Transcoding VOBs to {output_format} and outputting to {vob_path}"
                )
                if ffmpeg_move_VOBS_to_local(
                    iso,
                    mount_point,
                    ffmpeg_command,
                    ffprobe_command,
                    transcode_string,
                    output_ext,
                    output_path,
                    verbose,
                ):
                    print(
                        f"[+] Finished transcoding VOBs to {output_format}"
                    )
                    # Concatenate vobs into a single file, format of the user's selection
                    print(f"[-] Concatenating {output_format} files from {vob_path}")
                    errors = ffmpeg_concatenate_VOBS(
                        iso, output_ext, ffmpeg_command, output_path, verbose, overwrite
                    )
                    if not errors:
                        print(f"[+] Finished concatenating {output_format} files")
                        left_to_process.remove(iso)
                    else:
                        print(f"[!] Encountered an error processing {iso}")
                else:
                    print("[!] No VOBs found.")
            elif mode == 3:
                print(f"[-] Moving VOBs to {vob_path} and concatenating")
                if py_move_VOBS_to_local(
                    iso, mount_point, output_path
                ):
                    print(f"[+] Finished moving and concatenating VOBs in {vob_path}")
                    # Transcode vobs into the target format
                    print(f"[-] Transcoding VOBs in {vob_path} to {output_format}")
                    errors = concat_transcode_VOBS(
                        iso, transcode_string, output_ext, ffmpeg_command, ffprobe_command, output_path, verbose
                    )
                    if not errors:
                        print(f"[+] Finished transcoding VOBs to {output_format}")
                        left_to_process.remove(iso)
                    else:
                        print(f"[!] Encountered an error processing {iso}")
                else:
                    print("[!] No VOBs found or errors detected.")

            # CLEANUP
            print("[-] Removing Temporary Files")
            remove_temp_files(iso, output_path)
            # Delete all of the leftover files
            print("[+] Finished Removing Temporary Files")

            # This part unmounts the iso
            print(f"[-] Unmounting {iso}")
            if system == 'Windows':
                unmount_Win_Image(iso, unmount_cmd)
            else:
                unmount_Image(mount_point, unmount_cmd)
            print(f"[+] Unmounted {iso}")
            if system != 'Windows':
                try:
                    print(f"[-] Removing mount point {mount_point}")
                    os.rmdir(mount_point)
                except PermissionError:
                    print(
                        f"[!] Unable to remove the {mount_point} mount point. Manual removal may be required."
                    )
                    pass

        # If the user quits the script mid-processes the script cleans up after itself
        except KeyboardInterrupt:
            print(f"{bcolors.FAIL}[!] User has quit the script{bcolors.ENDC}")
            try:
                if system != 'Windows':
                    unmount_Image(mount_point, unmount_cmd)
                else:
                    unmount_Win_Image(iso, unmount_cmd)
                remove_temp_files(iso, output_path)
            except:
                pass
            sys.exit(1)

        print('-----------------------')
    print(f"[+] Completed processing {total_files - len(left_to_process)} ISO files.")
    if len(left_to_process) > 0:
        print("[!] The following files did not get converted:")
        for file in left_to_process:
            print(f"  - {file}")


# FUNCTION DEFINITIONS


def mount_Image(ISO_Path, mount_pts, mount_cmd):
    mount_point_exists = True
    mount_increment = 0

    # Determine next mountpoint
    while mount_point_exists:
        mount_point = f"ISO_Volume_{str(mount_increment)}"
        mount_point_exists = os.path.isdir(f"{mount_pts}{mount_point}")
        mount_increment += 1

    # Mount ISO
    try:
        mount_point = f"{mount_pts}{mount_point}"
        mount_command = f"{mount_cmd} '{ISO_Path}' {mount_point}"
        os.mkdir(mount_point)
        mount_return = run_command(mount_command)
        if mount_return == 1:
            print(f"{bcolors.FAIL}[!] Mounting Failed. Quitting Script{bcolors.ENDC}")
            sys.exit(1)
        return mount_point
    except PermissionError:
        print(
            f"{bcolors.FAIL}[!] Mounting failed due to permission error. Try running script in sudo / admin mode{bcolors.ENDC}"
        )
        sys.exit(1)


def unmount_Image(mount_point, unmount_cmd):
    unmount_command = f"{unmount_cmd} '{mount_point}'"
    run_command(unmount_command)
    return True

def test(all_args):
    #function(all_args["i"], all_args["o"])
    sys.exit(0)

def mount_Win_Image(iso, mount_cmd):
    iso = os.path.normpath(iso)
    full_mount_cmd = f'{mount_cmd} "{iso}" | Get-Volume | Select -Expand DriveLetter'
    try:
        mount = run_win_command(full_mount_cmd)
        return mount.stdout.rstrip()
    except Exception as e:
        print(e)

def unmount_Win_Image(iso, unmount_cmd):
    iso = os.path.normpath(iso)
    try:
        unmount = run_win_command(f'{unmount_cmd} "{iso}"')
        time.sleep(3)
    except Exception as e:
        print(e)

def cat_move_VOBS_to_local(file_path, mount_point, output_path):

    file_name_root = os.path.splitext(os.path.basename(file_path))[0]
    input_vobList = []
    input_discList = []
    lastDiscNum = 1
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS{os.sep}"

    # Find all of the vobs to be concatenated
    for dirName, _, fileList in os.walk(mount_point):
        for fname in fileList:
            if fname.split("_")[0] == "VTS" and fname.split(".")[-1] == "VOB":
                discNum = fname.split("_")[1]
                discNumInt = discNum.split("_")[0]
                vobNum = fname.split("_")[-1]
                vobNum = vobNum.split(".")[0]
                vobNumInt = int(vobNum)
                discNumInt = int(discNum)
                if discNumInt == lastDiscNum:
                    if vobNumInt > 0:
                        input_vobList.append(f"{dirName}/{fname}")
                if discNumInt > lastDiscNum:
                    input_vobList.sort()
                    input_discList.append(input_vobList)
                    input_vobList = []
                    if vobNumInt > 0:
                        input_vobList.append(f"{dirName}/{fname}")
                lastDiscNum = discNumInt

    # Returns False if there are no VOBs found, otherwise it moves on
    if len(input_vobList) == 0:
        has_vobs = False
    else:
        has_vobs = True
        input_vobList.sort()
        input_discList.append(input_vobList)

    try:
        os.mkdir(out_dir)
    except OSError:
        pass

    # This portion performs the copy of the VOBs to the local storage. They are moved using the bash `cat` command

    cat_command = ""
    output_disc_count = 1
    out_vob_path = f"{out_dir}{file_name_root}"

    if len(input_discList) > 1:

        for disc in input_discList:
            cat_command += "/bin/cat "
            for vob in disc:
                cat_command += f"{vob} "
            cat_command += f"> '{out_vob_path}_{str(output_disc_count)}.vob' && "
            output_disc_count += 1

        cat_command = cat_command.strip(" &&")

    else:
        cat_command += "cat "
        for disc in input_discList:
            for vob in disc:
                cat_command += f"{vob} "
            cat_command += f"> '{out_vob_path}.vob'"

    run_command(cat_command)
    return has_vobs


def ffmpeg_move_VOBS_to_local(
    file_path, mount_point, ffmpeg_command, ffprobe_command, transcode_string, output_ext, output_path, verbose
):
    input_vobList = []
    output_path = os.path.abspath(output_path)
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS{os.sep}"

    # Find all of the vobs to be concatenated
    for dirName, _, fileList in os.walk(mount_point):
        for fname in fileList:
            if fname.split("_")[0] == "VTS" and fname.split(".")[-1] == "VOB":
                vobNum = fname.split("_")[-1]
                vobNum = vobNum.split(".")[0]
                vobNum = int(vobNum)
                if vobNum > 0:
                    input_vobList.append(f"{dirName}{os.sep}{fname}")

    # Returns False if there are no VOBs found, otherwise it moves on
    if len(input_vobList) == 0:
        has_vobs = False
    else:
        has_vobs = True
        input_vobList.sort()

    try:
        os.mkdir(out_dir)
    except OSError:
        pass

    # This portion performs the copy of the VOBs to the SAN. They are concatenated after the copy so the streams are in the right order
    ffmpeg_command = os.path.normpath(ffmpeg_command)
    for v in input_vobList:
        v_name = v.split(os.sep)[-1]
        v_name = v_name.replace(".VOB", output_ext)
        out_vob_path = os.path.normpath(f'"{out_dir}{v_name}"')
        v = os.path.normpath(f'"{v}"')
        if ffprobe_command and '-s 640x480' in transcode_string:
            if platform.system() != 'Windows':
                try:
                    get_res = run_command(f"{ffprobe_command} -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 {v}")
                    get_res = get_res.stdout.rstrip().split(',')
                    source_res = f"{get_res[0]}x{get_res[1]}"
                    transcode_string = transcode_string.replace('640x480',source_res)
                except Exception:
                    pass
            else:
                try:
                    get_res = run_win_command(f"{ffprobe_command} -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 {v}")
                    get_res = get_res.stdout.rstrip().split(',')
                    source_res = f"{get_res[0]}x{get_res[1]}"
                    transcode_string = transcode_string.replace('640x480',source_res)
                except Exception:
                    pass        
        ffmpeg_vob_copy_string = f'{ffmpeg_command} -i {v} -map 0:v:0 -map 0:a:0 -video_track_timescale 90000 -af apad -shortest -avoid_negative_ts make_zero -fflags +genpts -b:a 192k {transcode_string} {out_vob_path}'
        if platform.system() == 'Windows':
            run_win_command(ffmpeg_vob_copy_string, powershell=False, capture_output=(not verbose))
        else:
            run_command(ffmpeg_vob_copy_string)

    # See if mylist already exists, if so delete it.
    remove_cat_list(file_path, output_path)

    # Write list of vobs to concat
    f = open(f"{file_path}.mylist.txt", "w")
    for v in input_vobList:
        v_name = v.split(os.sep)[-1]
        v_name = v_name.replace(".VOB", output_ext)
        out_vob_path = f"{out_dir}{v_name}"
        f.write(f"file '{out_vob_path}'")
        f.write("\n")
    f.close()

    return has_vobs

def py_move_VOBS_to_local(file_path, mount_point, output_path):
    clean = True
    file_name_root = os.path.splitext(os.path.basename(file_path))[0]
    input_vobList = []
    input_discList = []
    lastDiscNum = 1
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS{os.sep}"

    # Find all of the vobs to be concatenated
    for dirName, _, fileList in os.walk(mount_point):
        for fname in fileList:
            if fname.split("_")[0] == "VTS" and fname.split(".")[-1] == "VOB":
                discNum = fname.split("_")[1]
                discNumInt = discNum.split("_")[0]
                vobNum = fname.split("_")[-1]
                vobNum = vobNum.split(".")[0]
                vobNumInt = int(vobNum)
                discNumInt = int(discNum)
                if discNumInt == lastDiscNum:
                    if vobNumInt > 0:
                        input_vobList.append(os.path.normpath(f"{dirName}{os.sep}{fname}"))
                if discNumInt > lastDiscNum:
                    input_vobList.sort()
                    input_discList.append(input_vobList)
                    input_vobList = []
                    if vobNumInt > 0:
                        input_vobList.append(os.path.normpath(f"{dirName}{os.sep}{fname}"))
                lastDiscNum = discNumInt

    # Returns False if there are no VOBs found, otherwise it moves on
    if len(input_vobList) == 0:
        has_vobs = False
    else:
        has_vobs = True
        input_vobList.sort()
        input_discList.append(input_vobList)

    try:
        os.mkdir(out_dir)
    except OSError:
        pass

    # This portion performs the copy of the VOBs to the local storage. They are moved using simple python byte read/write.

    out_vob_path = os.path.normpath(f"{out_dir}{file_name_root}")

    with open(f"{out_vob_path}.vob", "wb") as dest:
        for disc in input_discList:
            for vob in disc:
                with open(vob, "rb") as src:
                    try:
                        while chunk := src.read(1024 * 1024):
                            dest.write(chunk)
                    except OSError as e:
                        print(f"[!] Unable to process {vob} - skipping")
                        clean = False
                        continue
    return has_vobs and clean

def concat_transcode_VOBS(
    file_path, transcode_string, output_ext, ffmpeg_command, ffprobe_command, output_path, verbose
):
    errors = False
    extension = os.path.splitext(file_path)[1]
    file_name = os.path.basename(file_path)
    output_path = os.path.abspath(output_path)
    if ffprobe_command != '':
        ffprobe_command = os.path.normpath(ffprobe_command)
    else:
        ffprobe_command = False
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS{os.sep}"
    vob_folder_path = f"{out_dir}"
    vob_list = []
    for v in os.listdir(vob_folder_path):
        if not v.startswith("."):
            if v.endswith(".vob"):
                vob_list.append(f"{out_dir}{v}")

    if len(vob_list) == 1:
        output_path = os.path.normpath(f'{output_path}{file_name.replace(extension,output_ext)}')
        vob_file = os.path.normpath(f'"{vob_list[0]}"')
        if ffprobe_command and '-s 640x480' in transcode_string:
            if platform.system() != 'Windows':
                try:
                    get_res = run_command(f"{ffprobe_command} -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 {vob_file}")
                    get_res = get_res.stdout.rstrip().split(',')
                    source_res = f"{get_res[0]}x{get_res[1]}"
                    transcode_string = transcode_string.replace('640x480',source_res)
                except Exception:
                    pass
            else:
                try:
                    get_res = run_win_command(f"{ffprobe_command} -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 {vob_file}")
                    get_res = get_res.stdout.rstrip().split(',')
                    source_res = f"{get_res[0]}x{get_res[1]}"
                    transcode_string = transcode_string.replace('640x480',source_res)
                except Exception:
                    pass
        ffmpeg_command = os.path.normpath(ffmpeg_command)
        ffmpeg_vob_concat_string = f'{ffmpeg_command} -i {vob_file} -dn -map 0:v:0 -map 0:a:0{transcode_string}"{output_path}"'
        if os.path.exists(output_path) and ' -n ' in transcode_string:
            print(f"[!] {output_path} exists and overwrite is set to 'NO', destination will not be overwritten")
        else:
            if platform.system() != 'Windows':
                result = run_command(ffmpeg_vob_concat_string)
                if result.returncode != 0:
                    errors = True
            else:
                result = run_win_command(ffmpeg_vob_concat_string, powershell=False, capture_output=(not verbose))
                if result.returncode != 0:
                    errors = True
    else:
        inc = 1
        for vob_path in vob_list:
            output_path = (
                os.path.normpath(f'{output_path}{file_name.replace(extension,"")}_{str(inc)}{output_ext}')
            )
            vob_path = os.path.normpath(vob_path)
            if ffprobe_command and '-s 640x480' in transcode_string:
                if platform.system() != 'Windows':
                    try:
                        get_res = run_command(f"{ffprobe_command} -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 {vob_path}")
                        get_res = get_res.stdout.rstrip().split(',')
                        source_res = f"{get_res[0]}x{get_res[1]}"
                        transcode_string = transcode_string.replace('640x480',source_res)
                    except Exception:
                        pass
                else:
                    try:
                        get_res = run_win_command(f"{ffprobe_command} -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 {vob_path}")
                        get_res = get_res.stdout.rstrip().split(',')
                        source_res = f"{get_res[0]}x{get_res[1]}"
                        transcode_string = transcode_string.replace('640x480',source_res)
                    except Exception:
                        pass            
            ffmpeg_vob_concat_string = (
                f'{ffmpeg_command} -i {vob_path} {transcode_string} "{output_path}"'
            )
            if os.path.exists(output_path) and ' -n ' in transcode_string:
                print(f"[!] {output_path} exists and overwrite is set to 'NO', destination will not be overwritten")
            else:
                if platform.system() != 'Windows':
                    result = run_command(ffmpeg_vob_concat_string)
                    if result.returncode != 0:
                        errors = True
                else:
                    result = run_win_command(ffmpeg_vob_concat_string, powershell=False, capture_output=(not verbose))
                    if result.returncode != 0:
                        errors = True
                inc += 1
    return errors

def ffmpeg_concatenate_VOBS(
    file_path, output_ext, ffmpeg_command, output_path, verbose, overwrite
):
    errors = False
    ffmpeg_command = os.path.normpath(ffmpeg_command)
    catList = os.path.normpath(f'"{file_path}.mylist.txt"')
    extension = os.path.splitext(file_path)[1]
    file_name = os.path.basename(file_path)
    output_path = os.path.abspath(output_path)
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    output_path = os.path.normpath(f'{output_path}{file_name.replace(extension,output_ext)}')
    ffmpeg_vob_concat_string = (
        f'{ffmpeg_command} -f concat -safe 0 -i {catList} -c copy "{output_path}"'
    )
    if overwrite:
        ffmpeg_vob_concat_string += " -y "
    if os.path.exists(output_path) and not overwrite:
        print(f"[!] {output_path} exists and overwrite is set to 'NO', destination will not be overwritten")
    else:
        if platform.system() != 'Windows':
            result = run_command(ffmpeg_vob_concat_string)
            if result.returncode != 0:
                errors = True
        else:
            result = run_win_command(ffmpeg_vob_concat_string, powershell=False, capture_output=(not verbose))
            if result.returncode != 0:
                errors = True
        remove_cat_list(file_path, output_path)
    return errors

def run_win_command(command, powershell=True, capture_output=True):
    try:
        if powershell:
            run = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=capture_output, text=True)
        else:
            run = subprocess.run(command, capture_output=capture_output, text=True)
        return run
    except Exception as e:
        print(e)
        return e

def run_command(command):
    try:
        run = subprocess.call([command], shell=True)
        return run
    except Exception as e:
        print(e)
        return e


def remove_temp_files(file, output_dir):
    temp_path = f"{output_dir}{os.path.basename(file)}"
    for the_file in os.listdir(f"{temp_path}.VOBS"):
        file_path = os.path.join(f"{temp_path}.VOBS", the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(e)
    os.rmdir(f"{temp_path}.VOBS")
    remove_cat_list(file, output_dir)


def remove_cat_list(file, output_dir):
    cat_file = f"{output_dir}{os.path.basename(file)}.mylist.txt"
    if os.path.exists(cat_file):
        try:
            os.remove(cat_file)
            print(f"[-] Removing Cat List {cat_file}")
        except OSError:
            pass


def dir_recurse(path, recursive=True):
    pattern = f"{path}/**"
    files = glob.glob(pattern, recursive=recursive)
    return files


# Used to make colored text
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


if __name__ == "__main__":
    main()
