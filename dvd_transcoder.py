#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BAVC DVD Transcoder
# Version History
#   2.0.0-rc1 - 20241211
#       set to be system agnostic (Linux and Mac currently, Windows incoming). Improved recursive and multi-file processing
#   1.0.0 - 20220907
#       improved error handling, removed old python2 code, removed unused imports. Prime Time!
#   0.2.0 - 20220906
#       Combined Bash Cat and FFmpeg Cat into a single script.
#
#
#
#
# import modules used here -- sys is a very standard one
import os
import sys
import glob
import subprocess  # used for running ffmpeg, qcli, and rsync
import argparse  # used for parsing input arguments
import platform

__version__ = "2.0.0-rc1"


def main():

    if platform.system() == "Linux":
        mount_cmd = "mount"
        unmount_cmd = "umount"
        mount_pts = "/mnt/"
        ffmpeg_path = subprocess.run(
            ["which", "ffmpeg"], capture_output=True, text=True
        )
        ffmpeg_command = f"{(ffmpeg_path.stdout).rstrip()} "
    elif platform.system() == "Darwin":
        mount_cmd = "hdiutil attach"
        unmount_cmd = "hdiutil detach"
        mount_pts = "/Volumes/"
        ffmpeg_path = subprocess.run(
            ["which", "ffmpeg"], capture_output=True, text=True
        )
        ffmpeg_command = f"{(ffmpeg_path.stdout).rstrip()} "
    elif platform.system() == "Windows":
        mount_cmd = "powershell Mount-DiskImage -ImagePath"
        unmount_cmd = "powershell Dismount-DiskImage -DevicePath"
        mount_pts = None
        ffmpeg_path = subprocess.run(
            ["where", "ffmpeg"], capture_output=True, text=True
        )
        ffmpeg_command = f"{(ffmpeg_path.stdout).rstrip()} "
    media_info_list = []

    ####init the stuff from the cli########
    parser = argparse.ArgumentParser(
        description=f"dvd_transcoder version {__version__}: Creates a concatenated video file from an DVD-Video ISO"
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="i",
        help="the path to the input directory or files",
        required=True,
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="f",
        help="The output format (defaults to v210. Pick from v210, ProRes, H.264, FFv1)",
        default="v210",
    )
    parser.add_argument(
        "-m",
        "--mode",
        dest="m",
        type=int,
        help="Selects concatenation mode. 1 = Simple Bash Cat, 2 = FFmpeg Cat",
        default=1,
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="o",
        help="the output folder path (optional, defaults to the same as the input)",
    )
    parser.add_argument(
        "-r",
        "--recurse",
        dest="r",
        help="if the input path is a directory, recursively search for all ISO's",
        action="store_true",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="v",
        action="store_true",
        default=False,
        help="run in verbose mode (including ffmpeg info)",
    )
    args = parser.parse_args()

    if args.m == 1:
        print(f"{bcolors.OKGREEN}Running in Simple Bash Cat mode{bcolors.ENDC}")
        mode = args.m
    elif args.m == 2:
        print(f"{bcolors.OKGREEN}Running in FFmpeg Cat mode{bcolors.ENDC}")
        mode = args.m
    else:
        print(f"{bcolors.FAIL}Please select a valid mode (1 or 2)!{bcolors.ENDC}")
        sys.exit(1)
    if args.f is None:
        output_format = "ProRes"
        transcode_string = " -c:v prores -profile:v 3 -c:a pcm_s24le -ar 48000 "
        output_ext = ".mov"
    elif "v210" in args.f:
        output_format = "v210"
        transcode_string = " -movflags write_colr+faststart -color_primaries smpte170m -color_trc bt709 -colorspace smpte170m -color_range mpeg -vf 'setfield=bff,setdar=4/3' -c:v v210 -c:a pcm_s24l -ar 48000 "
        output_ext = ".mov"
    elif "ProRes" in args.f:
        output_format = "ProRes"
        transcode_string = " -c:v prores -profile:v 3 -c:a pcm_s24le -ar 48000 "
        output_ext = ".mov"
    elif "H.264" in args.f:
        output_format = "H.264"
        transcode_string = " -c:v libx264 -pix_fmt yuv420p -movflags faststart -b:v 3500000 -b:a 160000 -ar 48000 -s 640x480 -vf yadif "
        output_ext = ".mp4"
    elif "FFv1" in args.f:
        output_format = "FFv1"
        transcode_string = " -map 0 -dn -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slicecrc 1 -slices 24 -field_order bb -color_primaries smpte170m -color_trc bt709 -colorspace smpte170m -c:a copy "
        output_ext = ".mkv"
    else:
        print("Please choose a valid output format from: v210, ProRes, H.264, FFv1")
        sys.exit(1)
    if args.o is None:
        if args.i[-1] != os.sep:
            output_path = f"{os.path.dirname(args.i)}{os.sep}"
        else:
            output_path = f"{os.path.dirname(args.i)}"
    else:
        if args.o[-1] != os.sep:
            output_path = f"{args.o}{os.sep}"
        else:
            output_path = args.o
    if args.v:
        print("Running in Verbose Mode")
    else:
        ffmpeg_command = f"{ffmpeg_command}-hide_banner -loglevel panic "

    process_files = []
    if os.path.isdir(args.i):
        if args.r:
            dir_contents = dir_recurse(args.i)
        else:
            dir_contents = dir_recurse(args.i, recursive=False)
        for file in dir_contents:
            if os.path.splitext(file)[1].lower() == ".iso":
                process_files.append(file)
    else:
        process_files.append(args.i)

    process_files = sorted(process_files)
    for iso in process_files:
        # This parts mounts the iso
        print(f"Mounting ISO {iso}...")
        mount_point = mount_Image(iso, mount_pts, mount_cmd)
        print("Finished Mounting ISO!")

        vob_path = f"{output_path}{os.path.basename(iso)}.VOBS"
        ##this part processes the vobs
        try:
            ##move each vob over as a separate file, adding each vob to a list to be concatenated
            if mode == 1:
                print(f"Moving VOBs to {vob_path} and concatenating...")
                if cat_move_VOBS_to_local(
                    iso, mount_point, ffmpeg_command, output_path
                ):
                    print(f"Finished moving VOBs to {vob_path} and concatenating!")
                    # transcode vobs into the target format
                    print(f"Transcoding {vob_path} to {output_format}")
                    cat_transcode_VOBS(
                        iso, transcode_string, output_ext, ffmpeg_command, output_path
                    )
                    print(f"Finished transcoding VOBS to {output_format}!")
                else:
                    print("No VOBs found. Quitting!")
            elif mode == 2:
                print(
                    f"Transcoding VOBs to {output_format} and moving to local directory..."
                )
                if ffmpeg_move_VOBS_to_local(
                    iso,
                    mount_point,
                    ffmpeg_command,
                    transcode_string,
                    output_ext,
                    output_path,
                ):
                    print(
                        f"Finished transcoding VOBs to {output_format} and moving to local directory..."
                    )
                    # concatenate vobs into a sungle file, format of the user's selection
                    print(f"Concatenating {output_format} files...")
                    ffmpeg_concatenate_VOBS(
                        iso, transcode_string, output_ext, ffmpeg_command, output_path
                    )
                    print(f"Finished concatenating {output_format} files!")
                else:
                    print("No VOBs found. Quitting!")

            # CLEANUP
            print("Removing Temporary Files...")
            remove_temp_files(iso, output_path)
            # Delete all fo the leftover files
            print("Finished Removing Temporary Files!")

            # This parts unmounts the iso
            print("Unmounting ISO")
            unmount_Image(mount_point, unmount_cmd)
            print("Finished Unmounting ISO!")
            try:
                print(f"Removing mount point {mount_point}")
                os.rmdir(mount_point)
            except PermissionError:
                print(
                    f"Unable to remove the {mount_point} mount point. Manual removal may be required."
                )
                pass

        # If the user quits the script mid-processes the script cleans up after itself
        except KeyboardInterrupt:
            print(f"{bcolors.FAIL}User has quit the script{bcolors.ENDC}")
            try:
                unmount_Image(mount_point, unmount_cmd)
                remove_temp_files(iso, output_path)
            except:
                pass
            sys.exit(1)

    print("Completed conversion")


# FUNCTION DEFINITIONS


def mount_Image(ISO_Path, mount_pts, mount_cmd):
    mount_point_exists = True
    mount_increment = 0

    ##figure out what the mountpoint will be
    while mount_point_exists:
        mount_point = f"ISO_Volume_{str(mount_increment)}"
        mount_point_exists = os.path.isdir(f"{mount_pts}{mount_point}")
        mount_increment = mount_increment + 1

    ##mount ISO
    try:
        mount_point = f"{mount_pts}{mount_point}"
        mount_command = f"{mount_cmd} '{ISO_Path}' {mount_point}"
        os.mkdir(mount_point)
        mount_return = run_command(mount_command)
        if mount_return == 1:
            print(f"{bcolors.FAIL}Mounting Failed. Quitting Script{bcolors.ENDC}")
            sys.exit(1)
        return mount_point
    except PermissionError:
        print(
            f"{bcolors.FAIL}Mounting failed due to permission error. Try running script in sudo mode{bcolors.ENDC}"
        )
        sys.exit(1)


def unmount_Image(mount_point, unmount_cmd):
    unmount_command = f"{unmount_cmd} '{mount_point}'"
    run_command(unmount_command)
    return True


def cat_move_VOBS_to_local(file_path, mount_point, ffmpeg_command, output_path):

    file_name_root = os.path.splitext(os.path.basename(file_path))[0]
    input_vobList = []
    input_discList = []
    lastDiscNum = 1
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS/"

    # find all of the vobs we want to concatenate
    for dirName, subdirList, fileList in os.walk(mount_point):
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

    ##Returns False if there are no VOBs found, otherwise it moves on
    if len(input_vobList) == 0:
        has_vobs = False
    else:
        has_vobs = True
        input_vobList.sort()
        input_discList.append(input_vobList)

        ##this portion performs the copy of the VOBs to the local storage. They are moved using the cat bash command

    try:
        delset_path = os.path.dirname(file_path)
        os.mkdir(out_dir)
    except OSError:
        pass

    #       Creating the cat command here

    cat_command = ""
    output_disc_count = 1
    out_vob_path = f"{out_dir}{file_name_root}"

    if len(input_discList) > 1:

        for disc in input_discList:
            cat_command += "/bin/cat "
            for vob in disc:
                cat_command += vob + " "
            cat_command += f"> '{out_vob_path}_{str(output_disc_count)}.vob' && "
            output_disc_count += 1

        cat_command = cat_command.strip(" &&")

    else:
        cat_command += "cat "
        for disc in input_discList:
            for vob in disc:
                cat_command += vob + " "
            cat_command += f"> '{out_vob_path}.vob'"

    run_command(cat_command)
    return has_vobs


def ffmpeg_move_VOBS_to_local(
    file_path, mount_point, ffmpeg_command, transcode_string, output_ext, output_path
):

    input_vobList = []
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS/"

    # find all of the vobs we want to concatenate
    for dirName, subdirList, fileList in os.walk(mount_point):
        for fname in fileList:
            if fname.split("_")[0] == "VTS" and fname.split(".")[-1] == "VOB":
                vobNum = fname.split("_")[-1]
                vobNum = vobNum.split(".")[0]
                vobNum = int(vobNum)
                if vobNum > 0:
                    input_vobList.append(dirName + "/" + fname)

    ##Returns False if there are no VOBs found, otherwise it moves on
    if len(input_vobList) == 0:
        has_vobs = False
    else:
        has_vobs = True
        input_vobList.sort()

        ##this portion performs the copy of the VOBs to the SAN. They are concatenated after the copy so the streams are in the right order

    try:
        delset_path = os.path.dirname(file_path)
        os.mkdir(out_dir)
    except OSError:
        pass

    input_vobList_length = len(input_vobList)
    iterCount = 1
    for v in input_vobList:
        v_name = v.split("/")[-1]
        v_name = v_name.replace(".VOB", output_ext)
        out_vob_path = f"{out_dir}{v_name}"
        ffmpeg_vob_copy_string = f"{ffmpeg_command} -i {v} -map 0:v:0 -map 0:a:0 -video_track_timescale 90000 -af apad -shortest -avoid_negative_ts make_zero -fflags +genpts -b:a 192k -y {transcode_string} '{out_vob_path}'"
        run_command(ffmpeg_vob_copy_string)

    ##see if mylist already exists, if so delete it.
    remove_cat_list(file_path)

    # writing list of vobs to concat
    f = open(f"{file_path}.mylist.txt", "w")
    for v in input_vobList:
        v_name = v.split("/")[-1]
        v_name = v_name.replace(".VOB", output_ext)
        out_vob_path = f"{out_dir}{v_name}"
        f.write(f"file '{out_vob_path}'")
        f.write("\n")
    f.close()

    return has_vobs


def cat_transcode_VOBS(
    file_path, transcode_string, output_ext, ffmpeg_command, output_path
):
    extension = os.path.splitext(file_path)[1]
    file_name = os.path.basename(file_path)
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS/"
    vob_folder_path = f"{out_dir}"
    vob_list = []
    for v in os.listdir(vob_folder_path):
        if not v.startswith("."):
            if v.endswith(".vob"):
                vob_list.append(f"{out_dir}{v}")

    if len(vob_list) == 1:
        output_path = f"{output_path}{file_name.replace(extension,output_ext)}"
        ffmpeg_vob_concat_string = f"{ffmpeg_command} -i '{vob_list[0]}' -dn -map 0:v:0 -map 0:a:0 {transcode_string} '{output_path}'"
        run_command(ffmpeg_vob_concat_string)
    else:
        inc = 1
        for vob_path in vob_list:
            output_path = (
                f"{output_path}{file_name.replace(extension,'')}_{str(inc)}{output_ext}"
            )
            ffmpeg_vob_concat_string = (
                f"{ffmpeg_command} -i '{vob_path}' {transcode_string} '{output_path}'"
            )
            run_command(ffmpeg_vob_concat_string)
            inc += 1


def ffmpeg_concatenate_VOBS(
    file_path, transcode_string, output_ext, ffmpeg_command, output_path
):
    catList = f"{file_path}.mylist.txt"
    extension = os.path.splitext(file_path)[1]
    file_name = os.path.basename(file_path)
    if output_path[-1] == os.sep:
        pass
    else:
        output_path += os.sep
    out_dir = f"{output_path}{os.path.basename(file_path)}.VOBS/"
    output_path = f"{output_path}{file_name.replace(extension,output_ext)}"
    ffmpeg_vob_concat_string = (
        f"{ffmpeg_command} -f concat -safe 0 -i '{catList}' -c copy '{output_path}'"
    )
    run_command(ffmpeg_vob_concat_string)
    remove_cat_list(file_path)


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
    try:
        os.remove(cat_file)
        print("Removing Cat List")
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
