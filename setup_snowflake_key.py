#!/usr/bin/env python3
"""
Create an RSA key pair so dbt can log in to Snowflake without a password or MFA prompt.

Run it inside the project's virtual environment (the `cryptography` package
comes with dbt-snowflake):

    python setup_snowflake_key.py

It writes the private key to ~/.snowflake/rsa_key.p8 (keep this file private;
never commit it) and prints an ALTER USER statement. Run that statement in a
Snowflake worksheet to attach the public key to your user.
"""

import argparse
import getpass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=getpass.getuser().upper(),
                    help="Snowflake user name (default: your Windows user name, upper case)")
    ap.add_argument("--out", default=str(Path.home() / ".snowflake" / "rsa_key.p8"),
                    help="where to write the private key")
    args, _unknown = ap.parse_known_args()

    key_path = Path(args.out)
    if key_path.exists():
        raise SystemExit(f"{key_path} already exists. Delete it first if you want a new key.")
    key_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))

    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_body = "".join(line for line in public_pem.splitlines() if "-----" not in line)

    print(f"Private key written to: {key_path}")
    print("Use this path for private_key_path in profiles.yml (forward slashes work on Windows):")
    print(f"  {key_path.as_posix()}\n")
    print("Run this in a Snowflake worksheet (check the user name matches your login):\n")
    print(f"ALTER USER {args.user} SET RSA_PUBLIC_KEY='{public_body}';")


if __name__ == "__main__":
    main()
