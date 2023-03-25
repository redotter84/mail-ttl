#!/usr/bin/env python3

import argparse
import datetime
import email
import imaplib
import logging
import yaml

logging.getLogger().setLevel(logging.INFO)


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-s',
        '--server',
        help='Imap server',
        default='imap.gmail.com',
    )
    parser.add_argument(
        '-e',
        '--email',
        help='Email address',
        required=True,
    )
    parser.add_argument(
        '-p',
        '--password',
        help='Password',
        required=True,
    )
    parser.add_argument(
        '-c',
        '--config',
        help='Path to folders config',
        default='./config.yaml',
    )
    return parser.parse_args()


class MessagesCleaner:
    def __init__(self, server, address, password, config_path):
        self._imap_client = imaplib.IMAP4_SSL(server)
        self._imap_client.login(address, password)
        logging.info('Signed in successfully')
        self._config = self._read_config(config_path)

    def __del__(self):
        self._imap_client.close()
        self._imap_client.logout()

    def _read_config(self, path):
        with open(path) as file:
            return yaml.safe_load(file)

    def _get_allowed_date(self, ttl):
        delta = datetime.timedelta(**ttl)
        return datetime.datetime.now() - delta

    def _parse_date(self, date_str):
        parts = date_str.split()
        date_str = ' '.join(parts[1:5])
        date = datetime.datetime.strptime(date_str, '%d %b %Y %H:%M:%S')
        return date

    def _process_message(self, index, raw, allowed_date):
        msg = email.message_from_string(raw)
        date = self._parse_date(msg['Date'])
        if date >= allowed_date:
            return False
        logging.info(f'\t{msg["Date"]}: {msg["Subject"]}"')
        self._imap_client.store(index, '+FLAGS', '\\Deleted')

    def _clean_up_folder(self, name, allowed_date):
        logging.info('Cleaning up folder %s', name)
        _, total = self._imap_client.select(f'"{name}"')
        total = int(total[0].decode())
        logging.info('Found %s messages in total', total)

        _, indices = self._imap_client.search(None, 'ALL')
        indices = indices[0].split()
        allowed_date_str = allowed_date.strftime('%Y-%m-%d')
        logging.info(f'The following messages are older than {allowed_date_str}. They will be removed:')
        for index in indices:
            _, data = self._imap_client.fetch(index, '(RFC822)')
            raw = data[0][1].decode()
            self._process_message(index, raw, allowed_date)

        _, removed = self._imap_client.expunge()
        if len(removed) != 1 or removed[0] is not None:
            logging.info(f'Removed {len(removed)} messages')
        else:
            logging.info('No messages were removed')

    def clean_up(self):
        for folder in self._config:
            allowed_date = self._get_allowed_date(folder.get('ttl', {}))
            self._clean_up_folder(folder['name'], allowed_date)

def main():
    try:
        args = parse_args()
        cleaner = MessagesCleaner(args.server, args.email, args.password, args.config)
        cleaner.clean_up()
    except Exception as e:
        logging.exception('Something went wrong')


if __name__ == '__main__':
    main()
