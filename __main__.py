import argparse
import glob
import os
import pathlib
import re
from datetime import datetime

import win32utils
from win32utils import CopyParams


# changes "a" to "_" in "202301_a\IMG_1694.HEIC"
def remove_letter_suffix_from_folder(filePath):
    return re.sub("_[a-z]\\\\", "__\\\\", filePath)


# Loads paths of already imported files into a set
def load_already_imported_file_names(metadata_folder):
    already_imported_files_set = set()
    if metadata_folder is not None:
        if not os.path.exists(metadata_folder):
            raise Exception(f"{metadata_folder} does not exist")
        if not os.path.isdir(metadata_folder):
            raise Exception(f"{metadata_folder} is not a folder")
        else:
            for filename in glob.glob(os.path.join(metadata_folder, "*.txt")):
                print(f"Loading imported file list from '{filename}'")
                with open(filename, "r") as file:
                    for line in file:
                        filename = line.strip()
                        amendedFilename = remove_letter_suffix_from_folder(filename)
                        already_imported_files_set.add(amendedFilename)
    print(f"Loaded {len(already_imported_files_set)} imported files")
    return already_imported_files_set


# Resolves which files to import
def resolve_items_to_import(source_folder_absolute_display_name, source_shell_items_by_path,
                            already_imported_files_set):
    imported_file_set = set()
    not_imported_file_set = set()
    shell_items_to_copy = {}
    for path in sorted(source_shell_items_by_path.keys()):
        source_file_shell_item = source_shell_items_by_path[path]
        source_file_absolute_path = win32utils.get_absolute_name(source_file_shell_item)
        file_relative_path = remove_prefix(source_file_absolute_path, source_folder_absolute_display_name)
        file_relative_path = remove_prefix(file_relative_path, '\\')
        amended_file_path = remove_letter_suffix_from_folder(file_relative_path)
        if amended_file_path not in already_imported_files_set:
            shell_items_to_copy[file_relative_path] = source_file_shell_item
            imported_file_set.add(amended_file_path)
        else:
            not_imported_file_set.add(file_relative_path)
    return imported_file_set, not_imported_file_set, shell_items_to_copy


def remove_prefix(str, prefix):
    if not str.startswith(prefix):
        raise Exception(f"'{str}' should start with '{prefix}")
    return str[len(prefix):]


def copy_using_windows_shell(shell_items_to_copy_by_target_path, destination_base_path_str):
    target_folder_shell_item_by_path = {}
    copy_params_list = []
    count_files_to_copy = 0
    for destination_file_path in sorted(shell_items_to_copy_by_target_path.keys()):
        desination_full_path = os.path.join(destination_base_path_str, destination_file_path)
        desination_folder = os.path.dirname(desination_full_path)
        desination_filename = os.path.basename(desination_full_path)
        if desination_folder not in target_folder_shell_item_by_path:
            pathlib.Path(desination_folder).mkdir(parents=True, exist_ok=True)
            target_folder_shell_item = win32utils.get_shell_item_from_path(desination_folder)
            target_folder_shell_item_by_path[desination_folder] = target_folder_shell_item
        source_file_shell_item = shell_items_to_copy_by_target_path[destination_file_path]
        copy_params = CopyParams(source_file_shell_item, target_folder_shell_item_by_path[desination_folder],
                                 desination_filename)
        copy_params_list.append(copy_params)
        count_files_to_copy += 1
    print(f'Files to copy: {count_files_to_copy}')
    win32utils.copy_multiple_files(copy_params_list)


def write_imported_file_list_to_metadata_folder(metadata_folder, file_path_set):
    time_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    imported_files_metadata_path = os.path.join(metadata_folder, f"imported_{time_str}.txt")
    print(f"Writing '{imported_files_metadata_path}'")
    with open(imported_files_metadata_path, "w") as file:
        for filename in sorted(list(file_path_set)):
            file.write(f"{filename}\n")

def create_date_filter(input, before=True):
    try:
        input_date = datetime.strptime(input, "%Y%m%d")
    except ValueError:
        print(f"Invalid date string given: {input} - Skipped using it to filter")
        return False
    if before is True:
        return lambda this_date: input_date <= this_date
    elif before is False:
        return lambda this_date: input_date >= this_date 
    else:
        return False

def main(args):
    print(f"Program args: {args.__dict__}")

    date_filters = []
    if args.exclude_before:
        date_filters.append( create_date_filter(args.exclude_before, before=True) )
    if args.exclude_after:
        date_filters.append( create_date_filter(args.exclude_after, before=False) )

    source_folder_absolute_display_name = args.source
    destination_path_str = args.destination

    already_imported_files_set = load_already_imported_file_names(args.metadata_folder)

    source_folder_shell_folder = win32utils.get_shell_folder_from_absolute_display_name(
        source_folder_absolute_display_name)

    source_shell_items_by_path = win32utils.walk_dcim(
        source_folder_shell_folder,
        filters=date_filters,
        root_folder=True,
    )

    imported_file_set, not_imported_file_set, shell_items_to_copy_by_target_path = resolve_items_to_import(
        source_folder_absolute_display_name, source_shell_items_by_path, already_imported_files_set)

    print(f"Import {len(imported_file_set)} files")

    if args.skip_copy:
        print(f"skip-copy mode, skipping copying")
    elif len(shell_items_to_copy_by_target_path) > 0:
        copy_using_windows_shell(shell_items_to_copy_by_target_path, destination_path_str)
    else:
        print(f"Nothing to copy")

    if len(imported_file_set) > 0:
        write_imported_file_list_to_metadata_folder(args.metadata_folder, imported_file_set)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--metadata-folder', required=False)
    parser.add_argument('--skip-copy', required=False, action='store_true')
    parser.add_argument('--exclude-before', help="exclude files before this date (YYYYMMDD)")
    parser.add_argument('--exclude-after', help="exclude files after this date (YYYYMMDD)")
    main(parser.parse_args())
