#!/usr/bin/env python3
import os
import re
import yaml
import math

# Directorios de configuracion en Proxmox
LXC_CONF_DIR = "/etc/pve/lxc"
KVM_CONF_DIR = "/etc/pve/qemu-server"

# Directorio de salida para los YAML de Ansible
OUTPUT_DIR = "./proxmox_to_ansible"
os.makedirs(f"{OUTPUT_DIR}/lxc", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/kvm", exist_ok=True)


def ensure_output_dirs():
    """Asegura que los subdirectorios de salida existan."""
    os.makedirs(f"{OUTPUT_DIR}/lxc", exist_ok=True)
    os.makedirs(f"{OUTPUT_DIR}/kvm", exist_ok=True)


def clean_output_dir(path):
    """
    Elimina todo el contenido del directorio de salida
    sin borrar el directorio raiz.
    """
    if not os.path.exists(path):
        return

    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            os.unlink(item_path)
            continue

        if os.path.isdir(item_path):
            for root, _, files in os.walk(item_path):
                for file_name in files:
                    os.unlink(os.path.join(root, file_name))


def parse_conf_file(path):
    """Parsea un archivo .conf de Proxmox y lo convierte en diccionario."""
    data = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()
    return data


def sort_device_key(key):
    """Ordena claves tipo net0/scsi1 por indice numerico."""
    match = re.search(r"(\d+)$", key)
    if not match:
        return (key, 0)
    return (re.sub(r"\d+$", "", key), int(match.group(1)))


def remove_size_from_cdrom(value):
    """
    Si la entrada corresponde a media=cdrom, elimina el parametro size=.
    """
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if not parts:
        return value

    is_cdrom = any(
        part.lower() == "media=cdrom" or part.lower().startswith("media=cdrom")
        for part in parts[1:]
    )
    if not is_cdrom:
        return value

    clean_parts = [parts[0]]
    for part in parts[1:]:
        if part.lower().startswith("size="):
            continue
        clean_parts.append(part)

    return ",".join(clean_parts)


def parse_size_to_gb(size_token):
    """Convierte size=32G/1024M/1T a GB."""
    match = re.match(r"^(\d+)([MGT])$", str(size_token).strip(), re.IGNORECASE)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2).upper()

    if unit == "G":
        return amount
    if unit == "T":
        return amount * 1024
    if unit == "M":
        return max(1, int(math.ceil(amount / 1024)))
    return None


def normalize_disk_value_for_export(value):
    """
    Convierte discos a formato storage:GB cuando se puede.
    - CDROM: conserva valor sin size=.
    - Disco con size=: storage:size_gb
    """
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if not parts:
        return value

    head = parts[0]
    options = parts[1:]

    is_cdrom = any(
        opt.lower() == "media=cdrom" or opt.lower().startswith("media=cdrom")
        for opt in options
    )
    if is_cdrom:
        return remove_size_from_cdrom(value)

    if ":" not in head:
        return value

    storage = head.split(":", 1)[0]
    size_opt = next((opt for opt in options if opt.lower().startswith("size=")), None)
    if not size_opt:
        return value

    size_gb = parse_size_to_gb(size_opt.split("=", 1)[1])
    if size_gb is None:
        return value

    return f"{storage}:{size_gb}"


def filter_kvm_config_for_export(conf):
    """
    Deja solo parametros necesarios para creacion/actualizacion de VM.
    """
    filtered = {}

    base_keys = [
        "boot",
        "bootdisk",
        "cores",
        "memory",
        "name",
        "onboot",
        "ostype",
        "scsihw",
        "sockets",
    ]
    for key in base_keys:
        if key in conf:
            filtered[key] = conf[key]

    device_prefixes = ["net", "scsi", "ide", "sata", "virtio"]
    for prefix in device_prefixes:
        device_keys = sorted(
            [key for key in conf if re.match(rf"^{prefix}\d+$", key, re.IGNORECASE)],
            key=sort_device_key,
        )
        for key in device_keys:
            value = conf[key]
            if prefix in ["scsi", "ide", "sata", "virtio"]:
                value = normalize_disk_value_for_export(value)
            filtered[key] = value

    return filtered


def create_disk_volume(conf):
    """
    Extrae storage, tamano y mountoptions de rootfs para generar disk_volume.
    """
    rootfs = conf.get("rootfs", "")
    storage = "local"
    size = 20  # valor por defecto
    options = {}

    if rootfs:
        try:
            # Extraer storage (antes de la primera coma y antes de ":")
            storage_part = rootfs.split(",")[0]
            storage = storage_part.split(":")[0]

            # Extraer size=XXXG o size=XXXM
            match = re.search(r"size=(\d+)([GM])", rootfs, re.IGNORECASE)
            if match:
                size_value = int(match.group(1))
                unit = match.group(2).upper()
                if unit == "G":
                    size = size_value
                elif unit == "M":
                    size = int(size_value / 1024)  # convertir MB a GB

            # Extraer mountoptions
            match_opts = re.search(r"mountoptions=([\w;]+)", rootfs, re.IGNORECASE)
            if match_opts:
                options["mountoptions"] = match_opts.group(1)
        except Exception:
            pass

    disk_volume = {
        "disk_volume": {
            "storage": storage,
            "size": size,
        }
    }

    if options:
        disk_volume["disk_volume"]["options"] = options

    return disk_volume


def inject_commented_defaults(yaml_path):
    """
    Inserta root_password y ostemplate comentados dentro de config.
    """
    with open(yaml_path, "r") as f:
        lines = f.readlines()

    output = []
    inside_config = False
    injected = False

    for line in lines:
        output.append(line)

        if line.strip() == "config:":
            inside_config = True
            continue

        if inside_config and not injected:
            if re.match(r"\s+\w+:", line):
                output.insert(
                    len(output) - 1,
                    "  #root_password: \"changeme\"\n"
                    "  #ostemplate: \"local:vztmpl/changeme.tar.zst\"\n",
                )
                injected = True
                inside_config = False

    with open(yaml_path, "w") as f:
        f.writelines(output)


def export_lxc():
    """Exporta contenedores LXC a YAML."""
    for file in os.listdir(LXC_CONF_DIR):
        if file.endswith(".conf"):
            vmid = file.replace(".conf", "")
            conf = parse_conf_file(os.path.join(LXC_CONF_DIR, file))

            ansible_data = {
                "vmid": vmid,
                "type": "lxc",
                "config": conf,
            }

            # Agregar disk_volume automaticamente
            ansible_data.update(create_disk_volume(conf))

            conf.pop("rootfs", None)

            output_file = f"{OUTPUT_DIR}/lxc/lxc-{vmid}.yml"
            with open(output_file, "w") as f:
                yaml.safe_dump(
                    ansible_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            inject_commented_defaults(output_file)

            print(f"LXC exportado: {output_file}")


def export_kvm():
    """Exporta maquinas virtuales KVM a YAML."""
    for file in os.listdir(KVM_CONF_DIR):
        if file.endswith(".conf"):
            vmid = file.replace(".conf", "")
            conf = parse_conf_file(os.path.join(KVM_CONF_DIR, file))
            filtered_conf = filter_kvm_config_for_export(conf)

            ansible_data = {
                "vmid": vmid,
                "type": "kvm",
                "config": filtered_conf,
            }

            output_file = f"{OUTPUT_DIR}/kvm/vm-{vmid}.yml"
            with open(output_file, "w") as f:
                yaml.safe_dump(
                    ansible_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            print(f"KVM exportado: {output_file}")


def main():
    print("Limpiando directorio de salida...")
    clean_output_dir(OUTPUT_DIR)
    ensure_output_dirs()

    print("Exportando contenedores LXC...")
    export_lxc()

    print("Exportando maquinas virtuales KVM...")
    export_kvm()

    print("\nExportacion completa")


if __name__ == "__main__":
    main()
