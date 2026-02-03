#!/usr/bin/env python3
import os
import yaml
import re

# Directorios de configuración en Proxmox
LXC_CONF_DIR = "/etc/pve/lxc"
KVM_CONF_DIR = "/etc/pve/qemu-server"

# Directorio de salida para los YAML de Ansible
OUTPUT_DIR = "./proxmox_to_ansible"
os.makedirs(f"{OUTPUT_DIR}/lxc", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/kvm", exist_ok=True)


def parse_conf_file(path):
    """Parsea un archivo .conf de Proxmox y lo convierte en diccionario"""
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


def create_disk_volume(conf):
    """
    Extrae storage, tamaño y mountoptions de rootfs para generar disk_volume
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
            "size": size
        }
    }

    if options:
        disk_volume["disk_volume"]["options"] = options

    return disk_volume


def export_lxc():
    """Exporta contenedores LXC a YAML"""
    for file in os.listdir(LXC_CONF_DIR):
        if file.endswith(".conf"):
            vmid = file.replace(".conf", "")
            conf = parse_conf_file(os.path.join(LXC_CONF_DIR, file))

            ansible_data = {
                "vmid": vmid,
                "type": "lxc",
                "config": conf
            }

            # Agregar disk_volume automáticamente
            ansible_data.update(create_disk_volume(conf))

            conf.pop("rootfs", None)

            output_file = f"{OUTPUT_DIR}/lxc/lxc-{vmid}.yml"
            with open(output_file, "w") as f:
                yaml.dump(ansible_data, f, default_flow_style=False)
            print(f"LXC exportado: {output_file}")


def export_kvm():
    """Exporta máquinas virtuales KVM a YAML"""
    for file in os.listdir(KVM_CONF_DIR):
        if file.endswith(".conf"):
            vmid = file.replace(".conf", "")
            conf = parse_conf_file(os.path.join(KVM_CONF_DIR, file))

            ansible_data = {
                "vmid": vmid,
                "type": "kvm",
                "config": conf
            }

            # Para KVM, se puede agregar extracción de discos más adelante si se desea

            output_file = f"{OUTPUT_DIR}/kvm/vm-{vmid}.yml"
            with open(output_file, "w") as f:
                yaml.dump(ansible_data, f, default_flow_style=False)
            print(f"KVM exportado: {output_file}")


def main():
    print("Exportando contenedores LXC...")
    export_lxc()

    print("Exportando máquinas virtuales KVM...")
    export_kvm()

    print("\n✔ Exportación completa")


if __name__ == "__main__":
    main()
