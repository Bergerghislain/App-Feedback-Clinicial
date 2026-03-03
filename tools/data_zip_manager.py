import argparse
import base64
import getpass
import io
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import pyzipper

APP_DATA_KEY_FILE = ".data_access.key"
APP_DATA_OBFUSCATION_SECRET = b"AppFeedbackClinical"
APP_DATA_KEY_PREFIX = "AFCLINICAL"


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(data[index] ^ key[index % len(key)] for index in range(len(data)))


def encode_app_data_password(password: str) -> str:
    payload = f"{APP_DATA_KEY_PREFIX}:{password}".encode("utf-8")
    obfuscated = _xor_bytes(payload, APP_DATA_OBFUSCATION_SECRET)
    return base64.urlsafe_b64encode(obfuscated).decode("utf-8")


def write_app_key_file(password: str, key_file_path: Path):
    key_file_path.parent.mkdir(parents=True, exist_ok=True)
    key_file_path.write_text(encode_app_data_password(password) + "\n", encoding="utf-8")
    print(f"OK - Fichier de cle app genere: {key_file_path}")


def build_inner_zip_bytes(source_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as inner_zip:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                archive_name = Path("data") / file_path.relative_to(source_dir)
                inner_zip.write(file_path, arcname=str(archive_name))
    return buffer.getvalue()


def pack_data_folder(source_dir: Path, zip_path: Path, app_key_file: Optional[Path], password: Optional[str]):
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Dossier source introuvable: {source_dir}")

    if password:
        pwd_1 = password
    else:
        pwd_1 = getpass.getpass("Entrer le code d'acces pour data.zip: ")
        pwd_2 = getpass.getpass("Confirmer le code d'acces: ")
        if pwd_1 != pwd_2:
            raise ValueError("Les codes saisis ne correspondent pas.")

    if not pwd_1:
        raise ValueError("Le code d'acces ne peut pas etre vide.")

    payload_bytes = build_inner_zip_bytes(source_dir)

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with pyzipper.AESZipFile(
        zip_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zip_file:
        zip_file.setpassword(pwd_1.encode("utf-8"))
        # Un seul payload pour ne pas exposer les noms des JSON dans l'archive externe.
        zip_file.writestr("payload.bin", payload_bytes)

    print(f"OK - Archive chiffree creee: {zip_path}")
    if app_key_file is not None:
        write_app_key_file(pwd_1, app_key_file)


def unpack_data_zip(zip_path: Path, output_dir: Path):
    if not zip_path.exists() or not zip_path.is_file():
        raise FileNotFoundError(f"Archive introuvable: {zip_path}")

    pwd = getpass.getpass("Entrer le code d'acces de data.zip: ")
    if not pwd:
        raise ValueError("Le code d'acces ne peut pas etre vide.")

    output_dir.mkdir(parents=True, exist_ok=True)
    with pyzipper.AESZipFile(zip_path, "r") as zip_file:
        zip_file.pwd = pwd.encode("utf-8")
        zip_file.extractall(output_dir)

    payload_file = output_dir / "payload.bin"
    if payload_file.exists():
        with zipfile.ZipFile(payload_file, "r") as inner_zip:
            inner_zip.extractall(output_dir)
        payload_file.unlink(missing_ok=True)

    extracted_data = output_dir / "data"
    if extracted_data.exists():
        print(f"OK - Dossier decrypte: {extracted_data}")
    else:
        print(f"OK - Contenu dezippe dans: {output_dir}")


def remove_plain_data_folder(source_dir: Path):
    if source_dir.exists() and source_dir.is_dir():
        shutil.rmtree(source_dir)
        print(f"OK - Dossier supprime: {source_dir}")
    else:
        print(f"Info - Aucun dossier a supprimer: {source_dir}")


def main():
    parser = argparse.ArgumentParser(description="Pack/Unpack securise du dossier data.")
    parser.add_argument("action", choices=["pack", "unpack", "pack-and-hide"])
    parser.add_argument("--source", default="data", help="Dossier source pour pack (par defaut: data)")
    parser.add_argument("--zip", default="data.zip", help="Nom de l'archive zip (par defaut: data.zip)")
    parser.add_argument("--output", default=".", help="Dossier de sortie pour unpack (par defaut: .)")
    parser.add_argument(
        "--app-key-file",
        default=APP_DATA_KEY_FILE,
        help=f"Chemin du fichier de cle app auto (par defaut: {APP_DATA_KEY_FILE})",
    )
    parser.add_argument(
        "--no-app-key",
        action="store_true",
        help="Ne pas generer le fichier de cle app (utilisation manuelle uniquement).",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Code data.zip en clair (optionnel, sinon prompt interactif).",
    )
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    zip_path = Path(args.zip).resolve()
    output_dir = Path(args.output).resolve()
    app_key_file = None if args.no_app_key else Path(args.app_key_file).resolve()
    password = args.password.strip() or None

    if args.action == "pack":
        pack_data_folder(source_dir, zip_path, app_key_file, password)
        return

    if args.action == "pack-and-hide":
        pack_data_folder(source_dir, zip_path, app_key_file, password)
        remove_plain_data_folder(source_dir)
        return

    if args.action == "unpack":
        unpack_data_zip(zip_path, output_dir)
        return


if __name__ == "__main__":
    main()
