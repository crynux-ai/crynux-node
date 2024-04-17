import argparse
import subprocess
import sys
from datetime import datetime
import time
import json


def log_message(message, newline=True):
    sys.stderr.write(message)
    if newline:
        sys.stderr.write("\n")


def upload_package(args):
    process = subprocess.Popen(['xcrun', 'notarytool', 'submit', '--no-wait',
                                '--output-format', 'json',
                                '--apple-id', args.username,
                                '--team-id', args.team,
                                '--password', args.password, args.package],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log_message('>> Uploading dmg to apple')
    output, error = process.communicate()
    output_str = output.decode('utf-8')
    error_str = error.decode('utf-8')
    log_message("output: " + output_str)

    if error_str != "":
        log_message("error: " + error_str)

    output_json = json.loads(output_str)

    if output_json["message"] != "Successfully uploaded file":
        log_message("Upload file error")
        exit(1)

    uuid = output_json["id"]
    log_message('>> Job UUID: %s' % uuid)
    return uuid


def get_log(args, uuid):
    log_message('Retrieving logs...')
    process = subprocess.Popen(['xcrun', 'notarytool', 'log',
                                '--apple-id', args.username, '--team-id', args.team, '--password', args.password, uuid],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    output_str = output.decode('utf-8')
    error_str = error.decode('utf-8')

    if error_str != "":
        log_message("error: " + error_str)

    return output_str


def check_status(args, uuid):
    process = subprocess.Popen(['xcrun', 'notarytool', 'info',
                                '--output-format', 'json',
                                '--apple-id', args.username, '--team-id', args.team, '--password', args.password, uuid],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    output_str = output.decode('utf-8')
    error_str = error.decode('utf-8')

    log_message("output: " + output_str)

    if error_str != "":
        log_message("error: " + error_str)

    output_json = json.loads(output_str)

    in_progress = output_json["status"] == "In Progress"
    invalid = output_json["status"] == "Invalid"

    if invalid:
        log_message('[Error] Notarization failed')
        logs = get_log(args, uuid)
        log_message(logs)
        exit(1)

    return in_progress


def staple(args):
    process = subprocess.Popen(['xcrun', 'stapler', 'staple', args.package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    log_message(output.decode('utf-8'))
    log_message(error.decode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description="Notarizes supplied dmg by uploading it to apple servers.")
    parser.add_argument("--package", help="Path to the dmg file", action='store', required=True)
    parser.add_argument("--username", help="Apple ID username to use to notarize", action='store', required=True)
    parser.add_argument("--team", help="Team ID to use to notarize", action='store', required=True)
    parser.add_argument("--password", action='store', help="Password for the appleid.", required=True)
    args = parser.parse_args()

    if not args.package.endswith('.dmg'):
        log_message('Supplied package %s is not a dmg file' % args.package)
        exit(1)

    uuid = upload_package(args)

    while check_status(args, uuid):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message('[' + current_time + '] Notarization in progress. Checking back in 30s')
        time.sleep(30)
    log_message('>> Notarization successful')
    log_message('>> Stapling')
    staple(args)
    log_message('[Success] All done')


if __name__ == '__main__':
    main()
