"""Create a private administrator PIN hash; never print the PIN or hash to logs."""
import argparse
import getpass
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.pin_auth import make_pin_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stdin', action='store_true', help='Read the PIN and confirmation from two stdin lines.')
    args = parser.parse_args()
    if args.stdin:
        pin, confirm = sys.stdin.readline().strip(), sys.stdin.readline().strip()
    else:
        pin = getpass.getpass('New administrator PIN (4 digits): ')
        confirm = getpass.getpass('Confirm PIN: ')
    if pin != confirm:
        raise SystemExit('PIN confirmation does not match.')
    encoded = make_pin_hash(pin)
    target = root / 'local-data/auth/admin-pin.env'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text('AUTH_MODE=pin' + chr(10) + 'ADMIN_PIN_HASH=' + encoded + chr(10), encoding='utf-8')
    temporary.replace(target)
    print('Saved local-data/auth/admin-pin.env. Keep this file private and out of GitHub.')
    print('Copy its AUTH_MODE and ADMIN_PIN_HASH values into Render after deploying compatible code.')


if __name__ == '__main__':
    main()
