# pip install python-gnupg==0.4.6
# Download gnupg-w32cli-1.4.x.exe from ftp://ftp.gnupg.org/gcrypt/binary/
# Install and add to path
# export GNUPGHOME="D:\workspace\thetatauCMT\secrets"
import os
import gnupg

gpg = gnupg.GPG(gnupghome=fr"{os.getcwd()}/secrets")
# gpg = gnupg.GPG()
input_data = gpg.gen_key_input(
    name_email="Frank.Ventura@thetatau.org", name_real="Theta Tau CMT"
)
key = gpg.gen_key(input_data)
ascii_armored_public_keys = gpg.export_keys(key.fingerprint)
passphrase = input("Please enter passphrase")
ascii_armored_private_keys = gpg.export_keys(
    keyids=key.fingerprint, secret=True, passphrase=passphrase,
)

with open(rf"{os.getcwd()}/secrets/mykeyfile.asc", "w") as f:
    f.write(ascii_armored_public_keys)
    f.write(ascii_armored_private_keys)
