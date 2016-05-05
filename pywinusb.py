#!/usr/bin/env python3

import psutil, re, shutil, progressbar, os, argparse
import glob, parted
from shutil import copyfile

class Pywinusb:

    def copyCall(self, srcPath, dstPath):

        # create destination directory (if required)
        if not os.path.exists(dstPath):
            os.makedirs(dstPath)

        NumberOfFiles = 0
        FilesToCopy = []

        print('Creating directory structure...')
        for root, directories, filenames in os.walk(srcPath):
            for directory in directories:
                # create the directory structure
                trimmings = root + '/' + directory
                final = dstPath + trimmings.replace(srcPath, '')
                if not os.path.exists(final):
                    os.makedirs(final)

            for filename in filenames:
                FilesToCopy.append(os.path.join(root, filename))
                NumberOfFiles = NumberOfFiles + 1

        print('Number of files: ' + str(len(FilesToCopy)))

        # Lets perform the file copy...
        x = 0;
        progress = progressbar.ProgressBar()
        for i in progress(range(NumberOfFiles)):
            DstFile = str(FilesToCopy[x]).replace(srcPath, '')
            copyfile(FilesToCopy[x], dstPath + DstFile)
            x = x + 1

    def getDiskPartitions(self):
        print(psutil.disk_partitions())
        pass

    def getBlockDevices(self):

        pattern = re.compile('.*sd.*')
        matchedBlockDevices = []

        for device in glob.glob('/sys/block/*'):
            # print(device)
            device_path = '/dev/' + os.path.basename(device)
            if pattern.match(device):
                matchedBlockDevices.append(device_path)

        return matchedBlockDevices

    def getBlockDeviceSize(device):
        nr_sectors = open('/sys/block/' + device + '/size').read().rstrip('\n')
        sect_size = open('/sys/block/' + device + '/queue/hw_sector_size').read().rstrip('\n')

        # The sect_size is in bytes, so we convert it to GiB and then send it back
        return round((float(nr_sectors) * float(sect_size)) / (1024.0 * 1024.0 * 1024.0),0)

    def checkIsBlockDeviceRemovableMedia(blockDeviceName):
        try:
            temp = open('/sys/block/' + os.path.basename(blockDeviceName) + '/removable','r')
            if '1' in temp.readline():
                return True
            else:
                return False
        except (FileNotFoundError):
            return False


    def formatPartition(blockDevice,fs):
        device = parted.Device(blockDevice)
        disk = parted.Disk(device)
        disk.deleteAllPartitions()

        types = parted.PARTITION_NORMAL
        geometry = parted.Geometry(device, disk.maxPartitionStartSector, disk.maxPartitionLength)
        fs = parted.FileSystem(fs, geometry)
        constraint = device.getConstraint()

        # create our partition
        partition = parted.Partition(disk, types, fs, geometry)
        partition.setFlag(parted.PARTITION_BOOT)
        disk.addPartition(partition, constraint)
        #

        disk.commit()

    def mountISO(isopath):
        # mount the iso
        try:
            # todo: check return values!
            os.system("mkdir -p /mnt/pywinusb_temp")
            os.system("umount /mnt/pywinusb_temp")
            os.system("mount -t auto -o loop " + isopath + " /mnt/pywinusb_temp");
        except(OSError):
            print('Fatal Error: Unable to mount the ISO.')
            exit(1)

    def mountUSB(block_device):
        # mount the usb device's partition
        try:
            # todo: check return values!
            os.system("mkdir -p /mnt/pywinusb_usb")
            os.system("umount " + block_device + '1')
            os.system("mount -t auto " + block_device + '1' + " /mnt/pywinusb_usb");
        except(OSError):
            print('Fatal Error: Unable to mount the ISO.')
            exit(1)

    def writeMBR(target):
        # attempt to write the mbr to the block device
        try:
            # todo: check return values!
            os.system("/usr/bin/ms-sys -n -f " + target + '1')
        except(OSError):
            print('Fatal Error: Unable to write MBR to device.')
            exit(1)

    def setRWUSB(target):
        try:
            # todo: check return values!
            os.system("/usr/sbin/hdparm -r0 " + target)
        except(OSError):
            print('Fatal Error: Unable to write MBR to device.')
            exit(1)

    def createFileSystem(fs_type, block_device):
        try:
            if fs_type == 'ntfs':
                print('Formatting NTFS FS...')
                os.system("umount " + block_device)
                os.system("mkfs.ntfs -f " + block_device)
            elif fs_type == 'fat32':
                print('Formatting FAT32 FS...')
                os.system("umount " + block_device)
                os.system("mkdosfs -vF 32 " + block_device)
        except(OSError):
            print('Error: Failed to format the disk partition!')
            print('Exiting...')
            exit(1)

    ################
    # Start program
    ################

    # global vars
    interactive_mode = False
    fs_type = ''
    iso_path = ''
    boot_type = ''
    suitable_block_storage = {}
    blockSelection = ''
    working_directory = '/tmp/pywinusb_work/'

    print('PyWinUSB 1.0')
    print()

    # Logic to check if interactive or non-interactive mode started
    parser = argparse.ArgumentParser(description='PyWinUSB: Windows USB Creator')
    parser.add_argument('-t', action="store", dest='boot_type', help="The boot type - either uefi or bios.")
    parser.add_argument('-p', action="store", dest="iso_path", help="The full (absolute) path of the iso file.")
    parser.add_argument('-b', action="store", dest="blockSelection", help="The usb block device e.g. /dev/sdX.")
    args = parser.parse_args()
    globals().update(vars(parser.parse_args()))

    if args.boot_type == None and args.iso_path == None and args.blockSelection == None:
        print('Running in interactive mode.')
        interactive_mode = True

    # Validate input
    if (interactive_mode == False):
        if (args.boot_type != 'uefi' and 'bios'):
            print("""Error: -t switch accepts either 'bios' or 'uefi' """)
            exit(1)

    if  (interactive_mode == False):
        if (args.iso_path == None):
            print('No input defined for the -p switch!')
            exit(1)
        if (os.path.isfile(args.iso_path) != True):
            print("""Error: Please ensure the iso path is valid! """)
            exit(1)

    if (interactive_mode == False):
        if (args.blockSelection == None):
            print('No input defined for the -b switch!')
            exit(1)
        if (checkIsBlockDeviceRemovableMedia(args.blockSelection) != True):
            print("""Error: Please ensure the block device is a USB drive! """)
            exit(1)

    # Check root perms
    if os.geteuid() != 0:
        print('Please ensure this application is running with root privilages! Exiting...')
        exit()

    # Pre-req checks
    # Handled by packager.

    # Step 0: Select block device
    x = 0
    for blockDevice in getBlockDevices('self'):
        if checkIsBlockDeviceRemovableMedia(blockDevice):
            suitable_block_storage[x] = blockDevice
            print('Found removable media: ' + blockDevice + ' (Size: ~' + str(getBlockDeviceSize(os.path.basename(blockDevice))) + ' GiB)')


    if (len(suitable_block_storage) == 0):
        print('Error: No suitable block storage devices found!')
        print('Exiting...')
        exit(1)

    print()

    if (interactive_mode == False):
        blockSelection = args.blockSelection
    else:
        print('Please enter the block device ID (int) you wish to use for the installation: ')

        print("{:<8} {:<15}".format('ID', 'Label'))
        for key, value in suitable_block_storage.items():
            print("{:<8} {:<15}".format(key, value))

        valid_input = False;
        while (valid_input == False):
            user_selection = input()
            try:
                blockSelection = suitable_block_storage[int(user_selection)]
                valid_input = True;
            except(ValueError, KeyError):
                print('Error: Please enter a valid block device ID!')
                continue

    # Step 1: UEFI or BIOS?
    if (interactive_mode == False):
        if args.boot_type == 'bios':
            boot_type = 'bios'
            fs_type = 'ntfs'
        elif args.boot_type == 'uefi':
            boot_type = 'uefi'
            fs_type = 'fat32'
    else:
        ValidInput = False
        print()
        print("""Please select (by typing in) either 'uefi' or 'bios' mode:""")
        while (ValidInput == False):
            user_selection = input()
            if (user_selection == 'uefi' or user_selection == 'UEFI'):
                boot_type = 'uefi'
                fs_type = 'fat32'
                ValidInput = True
            elif (user_selection == 'bios' or user_selection == 'BIOS'):
                boot_type = 'bios'
                fs_type = 'ntfs'
                ValidInput = True
            else:
                print('Error: Please try again:')

    # Step 2: Format / partition device
    formatPartition(blockSelection, fs_type)
    createFileSystem(fs_type, blockSelection + '1')

    # Step 3: Mount ISO and copy data
    print()

    if (interactive_mode == False):
        iso_path = args.iso_path
    else:
        print('Please enter the filepath of the ISO file you wish to use:')

        ValidInput = False

        while (ValidInput == False):
            user_selection = input()
            # check file exists
            if (os.path.isfile(user_selection) != True):
                print('Error: Please ensure that the filepath is correct - please re-enter the path:')
            else:
                iso_path = user_selection
                ValidInput = True

    mountISO(iso_path)

    # Step 4: Copy iso data to working directory
    if not os.path.exists(working_directory):
        os.makedirs(working_directory)
    else:
        # lets cleanup...
        shutil.rmtree(working_directory)
        os.makedirs(working_directory)

    # perform copy operation
    copyCall('self','/mnt/pywinusb_temp', working_directory)

    # Step 5: BIOS OR UEFI
    if (boot_type == 'uefi'):
    # UEFI
        mount_path = '/mnt/pywinusb_temp/'
        if os.path.isfile(mount_path + 'efi/boot/bootx64.efi'):
            pass
        elif os.path.isfile(mount_path + 'efi/boot/bootia32.efi'):
            pass
        else:
            print('Not implemented. Sorry this ISO is not officially supported.')
            print('Attempting anyway...')
    else:
        # BIOS
        print('Writing MBR to device...')
        writeMBR(blockSelection)

    # Step 6: Copy files from working directory to USB device partition
    setRWUSB(blockSelection)
    mountUSB(blockSelection)
    copyCall('self', working_directory, '/mnt/pywinusb_usb/')
    # Cleanup...
    os.system("umount " + blockSelection + '1')
    shutil.rmtree(working_directory, ignore_errors=True)

    print()
    print('Success - the Windows USB installation has been completed!')
    exit(0)