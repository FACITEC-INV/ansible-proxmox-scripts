# Ansible Proxmox Scripts

Sistema de gestión de configuración (Infrastructure as Code) para servidores
Proxmox VE. Permite crear, actualizar, eliminar y exportar máquinas virtuales
(KVM) y contenedores (LXC) mediante playbooks de Ansible, usando la API REST
y tokens de autenticación.

## Índice

- [Estructura del proyecto](#estructura-del-proyecto)
- [Inventario de nodos](#inventario-de-nodos)
- [Datos de configuración](#datos-de-configuración)
- [Catálogo de playbooks](#catálogo-de-playbooks)
- [Ejemplos paso a paso](#ejemplos-paso-a-paso)

## Dependencias del sistema

| Dependencia | Versión | Propósito |
|---|---|---|
| [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) | ≥ 2.15 | Motor de automatización |
| `community.general` (colección Ansible) | ≥ 9.0 | Módulo `proxmox_vm_info` |
| `community.proxmox` (colección Ansible) | ≥ 1.0 | Módulos `proxmox_kvm`, `proxmox`, `proxmox_storage_contents_info` |
| Python 3 | ≥ 3.10 | Intérprete para Ansible y scripts auxiliares |
| PyYAML (`yaml`) | ≥ 6.0 | Procesamiento YAML en `tools/proxmox_to_ansible.py` |
| rsync | ≥ 3.0 | Sincronización en `proxmox_export.yml` |

Instalación de dependencias:

```bash
# Colecciones de Ansible
ansible-galaxy collection install community.general community.proxmox

# PyYAML (para el script de exportación)
pip install pyyaml
```

## Estructura del proyecto

```
proxmox-scripts/
├── ansible.cfg             # Configuración de Ansible (inventario)
├── .gitignore              # Ignora inventory/**/*.yml (credenciales)
├── inventory/
│   ├── hosts.yml            # Inventario de nodos Proxmox
│   ├── hosts.yml.example    # Ejemplo de inventario
│   └── host_vars/
│       ├── proxmox.yml      # Credenciales y rutas para nodo "prox"
│       ├── proxmox.yml.example
│       └── nodo2.yml        # Credenciales y rutas para cada nodo
├── playbooks/
│   ├── apply_vm.yml         # Crear o actualizar VMs KVM
│   ├── create_vm.yml        # Crear VMs KVM (solo nuevas)
│   ├── update_vm.yml        # Actualizar VMs KVM (solo existentes)
│   ├── apply_lxc.yml        # Crear o actualizar contenedores LXC
│   ├── list_vms.yml         # Listar VMs vía API
│   ├── list_images.yml      # Listar templates/ISOs disponibles
│   ├── delete-vm.yml        # Eliminar VM (ejecuta en remoto)
│   ├── delete-lxc.yml       # Eliminar LXC (ejecuta en remoto)
│   ├── lxc-vpn.yml          # Habilitar TUN/nesting en LXC (remoto)
│   ├── proxmox_export.yml   # Exportar configuración viva a YAML (remoto)
│   └── roles/
│       ├── kvm/tasks/       # Tareas de ciclo de vida KVM
│       └── lxc/tasks/       # Tareas de ciclo de vida LXC
├── config_example/
│   ├── kvm/vm-vmid.yml.example
│   └── lxc/lxc-vmid.yml.example
└── tools/
    └── proxmox_to_ansible.py  # Script de exportación
```

## Inventario de nodos

### hosts.yml

Define los nodos Proxmox, cada uno con dos variantes de conexión:

| Host | Conexión | Uso |
|---|---|---|
| `nodename` | Local (`ansible_connection: local`) | Playbooks de API: apply/create/update/list |
| `nodename_remote` | SSH (`ansible_host`, `ansible_user`, clave privada) | Playbooks de sistema: delete, lxc-vpn, export |
| (repetir para cada nodo) | Local + SSH | Ídem para nodos adicionales |

```yaml
# inventory/hosts.yml
all:
  hosts:
    nodo1:
      ansible_connection: local
      ansible_python_interpreter: "/ruta/a/python3"
    nodo1_remote:
      ansible_host: "10.0.0.10"
      ansible_user: "root"
      ansible_ssh_private_key_file: "~/.ssh/id_ed25519"
    nodo2:
      ansible_connection: local
      ansible_python_interpreter: "/ruta/a/python3"
    nodo2_remote:
      ansible_host: "10.0.0.20"
      ansible_user: "root"
      ansible_ssh_private_key_file: "~/.ssh/id_ed25519"
```

### host_vars/<host>.yml

Por cada nodo se define:

| Variable | Descripción |
|---|---|
| `proxmox_host` | IP o FQDN del servidor Proxmox |
| `proxmox_port` | Puerto de la API (8006 por defecto) |
| `proxmox_api_user` | Usuario de API (`root@pam`) |
| `proxmox_api_token_id` | ID del token de API |
| `proxmox_api_token_secret` | Secreto del token de API |
| `proxmox_node` | Nombre del nodo dentro del cluster |
| `storage_name` | Nombre del storage por defecto |
| `configs_dir` | Ruta absoluta al directorio de datos de configuración |

```yaml
# inventory/host_vars/nodo1.yml
proxmox_host: "10.0.0.10"
proxmox_port: "8006"
proxmox_api_user: "root@pam"
proxmox_api_token_id: "mi-token-id"
proxmox_api_token_secret: "mi-token-secreto"
proxmox_node: "nodo1"
storage_name: "local"
configs_dir: "/ruta/absoluta/datos-nodo1"
```

> [!IMPORTANT]
> `inventory/**/*.yml` está en `.gitignore` para evitar exponer credenciales.
> Usar `hosts.yml.example` y `host_vars/proxmox.yml.example` como plantillas.

## Datos de configuración

Cada VM o LXC se describe en un archivo YAML individual dentro del
`configs_dir` del nodo correspondiente.

### Convención de nombres

| Tipo | Archivo | Ejemplo |
|---|---|---|
| KVM | `kvm/vm-<VMID>.yml` | `kvm/vm-100.yml` |
| LXC | `lxc/lxc-<VMID>.yml` | `lxc/lxc-100.yml` |
| Imágenes | `images.yml` | `images.yml` |

### Archivo de configuración KVM (vm-<VMID>.yml)

```yaml
vmid: '100'
type: kvm
config:
  boot: order=sata0;ide2;net0;hostpci0
  bootdisk: scsi0
  cores: '4'
  memory: '4096'
  name: mi-vm-ejemplo
  onboot: '1'
  ostype: l26
  scsihw: virtio-scsi-single
  sockets: '1'
  net0: virtio=BC:24:11:9E:D7:A1,bridge=vmbr0
  ide2: none,media=cdrom
  sata0: local-lvm:256
```

**Campos de `config:`:**

| Campo | Obligatorio | Descripción |
|---|---|---|
| `name` | Sí | Nombre de la VM |
| `cores` | No | Número de cores |
| `sockets` | No | Número de sockets |
| `memory` | No | RAM en MB |
| `ostype` | No | Tipo de SO invitado (`l26` para Linux ≥ 2.6, `win11`, etc.) |
| `onboot` | No | Iniciar al arrancar el host (`1`/`0`) |
| `scsihw` | No | Controladora SCSI (`virtio-scsi-single`, `lsi`...) |
| `boot` | No | Orden de arranque |
| `bootdisk` | No | Disco de arranque (ej. `scsi0`) |
| `net0`..`netN` | No | Interfaces de red |
| `scsi0`..`scsiN` | No | Discos SCSI |
| `ide0`..`ideN` | No | Dispositivos IDE (CDROM) |
| `sata0`..`sataN` | No | Discos SATA |
| `virtio0`..`virtioN` | No | Discos VirtIO |

**Formato de discos:**

```
almacenamiento:tamaño_en_gb
```

Ejemplos:
- `local-lvm:256` → disco de 256 GB en storage `local-lvm`
- `local:iso/debian.iso,media=cdrom` → ISO montada como CDROM

**Formato de interfaces de red:**

```
tipo=MAC_OPCIONAL,bridge=vmbrN
```

Ejemplos:
- `virtio=BC:24:11:9E:D7:A1,bridge=vmbr0` → MAC fija
- `virtio,bridge=vmbr0` → MAC generada por Proxmox

### Archivo de configuración LXC (lxc-<VMID>.yml)

```yaml
vmid: '100'
type: lxc
config:
  arch: amd64
  cores: '4'
  dev0: /dev/net/tun
  features: keyctl=1,nesting=1
  hostname: mi-contenedor
  memory: '8192'
  net0: name=eth0,bridge=vmbr0,hwaddr=BC:24:11:F5:DC:BF,ip=dhcp,type=veth
  onboot: '1'
  ostype: ubuntu
  swap: '1024'
  unprivileged: '1'
  lxc.cgroup2.devices.allow: c 10:200 rwm
disk_volume:
  storage: main-storage
  size: 500
  options:
    mountoptions: lazytime;discard
```

**Campos de `config:`:**

| Campo | Obligatorio | Descripción |
|---|---|---|
| `hostname` | Sí | Nombre del contenedor |
| `ostype` | Sí | Tipo de SO (`debian`, `ubuntu`, `centos`...) |
| `cores` | No | Número de cores |
| `memory` | No | RAM en MB |
| `swap` | No | Swap en MB |
| `onboot` | No | Iniciar al arrancar (`1`/`0`) |
| `unprivileged` | No | Contenedor no privilegiado (`1`/`0`) |
| `features` | No | Características (`keyctl=1,nesting=1`) |
| `net0` | Sí | Interfaz de red |
| `arch` | No | Arquitectura (`amd64`) |
| `dev0` | No | Dispositivo (`/dev/net/tun`) |
| `ostemplate` | **Solo crear** | Template del contenedor |
| `root_password` | **Solo crear** | Contraseña root |

**Campo `disk_volume:`** (fuera de `config:`):

| Subcampo | Obligatorio | Descripción |
|---|---|---|
| `storage` | Sí | Nombre del storage |
| `size` | Sí | Tamaño en GB |
| `options.mountoptions` | No | Opciones de montaje |

> [!NOTE]
> `ostemplate` y `root_password` solo se usan en la creación inicial;
> aparecen comentados en los archivos exportados (el playbook los ignora
> si el contenedor ya existe).

### images.yml

Lista de imágenes ISO y templates LXC disponibles. Se genera con el
playbook `list_images.yml`.

```yaml
# configs_dir/images.yml
- {content: iso, format: iso, size: 822083584, volid: 'local:iso/debian-13.2.0-amd64-netinst.iso'}
- {content: vztmpl, format: tzst, size: 129710398, volid: 'local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst'}
```

## Catálogo de playbooks

### Parámetros comunes

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `-e server=<host>` | `nodo1` | Nodo destino (según el inventario) |
| `-e id=<VMID>` | (todos) | Filtrar una VM/LXC específica por ID |

---

### apply_vm.yml

**Propósito:** Crear o actualizar máquinas virtuales KVM.
**Operación:** `apply` (crea si no existe, actualiza si existe).
**Hosts:** `{{ server | default('proxmox') }}` (API local).

```bash
ansible-playbook playbooks/apply_vm.yml
ansible-playbook playbooks/apply_vm.yml -e server=nodo2
ansible-playbook playbooks/apply_vm.yml -e id=100
```

**Flujo de ejecución:**
1. Busca archivos `kvm/vm-*.yml` en `configs_dir`
2. Filtra por ID si se especificó `-e id`
3. Para cada archivo: lee la configuración, consulta el estado actual vía API
4. Crea o actualiza la VM con el módulo `proxmox_kvm`
5. Si el disco cambió (en existente): redimensiona vía API REST
6. Inicia la VM (si es nueva) o la reinicia (si hubo cambios)
7. Si es nueva: obtiene la MAC generada por Proxmox y la guarda en el YAML

---

### create_vm.yml

**Propósito:** Crear VMs KVM (solo si no existen).
**Operación:** `create` (ignora VMs existentes).
**Hosts:** `{{ server | default('proxmox') }}` (API local).

```bash
ansible-playbook playbooks/create_vm.yml
```

---

### update_vm.yml

**Propósito:** Actualizar VMs KVM existentes (omite las que no existen).
**Operación:** `update` (ignora VMs nuevas).
**Hosts:** `{{ server | default('proxmox') }}` (API local).

```bash
ansible-playbook playbooks/update_vm.yml
```

---

### apply_lxc.yml

**Propósito:** Crear o actualizar contenedores LXC.
**Operación:** `apply` siempre (crea si no existe, actualiza si existe).
**Hosts:** `{{ server | default('proxmox') }}` (API local).

```bash
ansible-playbook playbooks/apply_lxc.yml
ansible-playbook playbooks/apply_lxc.yml -e server=nodo2 -e id=100
```

**Flujo de ejecución:**
1. Busca archivos `lxc/lxc-*.yml` en `configs_dir`
2. Filtra por ID si se especificó `-e id`
3. Para cada archivo: lee la configuración, consulta el estado actual vía API
4. Crea o actualiza el contenedor con el módulo `proxmox`
5. `ostemplate` y `password` solo se pasan si el contenedor **no existe**
6. Si es nuevo: inicia el contenedor y obtiene la MAC vía API
7. Si el disco cambió: redimensiona vía API REST y reinicia

---

### list_vms.yml

**Propósito:** Listar todas las VMs KVM de un nodo vía API.
**Hosts:** `{{ server | default('proxmox') }}` (API local).

```bash
ansible-playbook playbooks/list_vms.yml
ansible-playbook playbooks/list_vms.yml -e server=nodo2
```

---

### list_images.yml

**Propósito:** Obtener templates LXC y archivos ISO del storage y guardarlos
en `configs_dir/images.yml`.
**Hosts:** `{{ server | default('proxmox') }}` (API local).

```bash
ansible-playbook playbooks/list_images.yml
```

---

### delete-vm.yml

**Propósito:** Eliminar una máquina virtual KVM.
**Hosts:** `{{ server | default('proxmox') }}_remote` (SSH remoto).
**Parámetros requeridos:** `-e id=<VMID>`

```bash
ansible-playbook playbooks/delete-vm.yml -e id=100
```

**Flujo:**
1. Verifica que la VM existe con `qm status`
2. La detiene si está en ejecución
3. La destruye con `qm destroy <VMID> --purge 1`

---

### delete-lxc.yml

**Propósito:** Eliminar un contenedor LXC.
**Hosts:** `{{ server | default('proxmox') }}_remote` (SSH remoto).
**Parámetros requeridos:** `-e id=<VMID>`

```bash
ansible-playbook playbooks/delete-lxc.yml -e id=100
```

---

### lxc-vpn.yml

**Propósito:** Habilitar TUN/tunel VPN y nesting en un contenedor LXC.
**Hosts:** `{{ server | default('proxmox') }}_remote` (SSH remoto).
**Parámetros requeridos:** `-e id=<VMID>`

```bash
ansible-playbook playbooks/lxc-vpn.yml -e id=100
```

**Qué hace:**
1. Ejecuta `pct set <VMID> --dev0 /dev/net/tun`
2. Ejecuta `pct set <VMID> --features keyctl=1,nesting=1`
3. Agrega `lxc.cgroup2.devices.allow: c 10:200 rwm` al archivo `.conf`
4. Reinicia el contenedor
5. Verifica que `/dev/net/tun` existe dentro del contenedor

---

### proxmox_export.yml

**Propósito:** Exportar la configuración actual de VMs y contenedores desde
un nodo Proxmox a archivos YAML listos para Ansible.
**Hosts:** `{{ server | default('proxmox') }}_remote` (SSH remoto).

```bash
ansible-playbook playbooks/proxmox_export.yml
ansible-playbook playbooks/proxmox_export.yml -e server=nodo2
```

**Flujo:**
1. Copia `tools/proxmox_to_ansible.py` al servidor remoto
2. Ejecuta el script, que lee `/etc/pve/lxc/*.conf` y `/etc/pve/qemu-server/*.conf`
   y genera YAML en `/root/proxmox_to_ansible/`
3. Descarga los resultados al `configs_dir` local mediante rsync

**Lo que exporta:**
- LXC: `lxc/lxc-<VMID>.yml` con `vmid`, `type`, `config` y `disk_volume` autocalculado
- KVM: `kvm/vm-<VMID>.yml` con campos esenciales filtrados (boot, cores, memory, net, discos...)
- Para LXC, inserta `root_password` y `ostemplate` como comentarios dentro de `config:`

## Ejemplos paso a paso

### 1. Sincronizar la configuración desde un nodo Proxmox

```bash
# 1. Listar imágenes disponibles y guardarlas localmente
ansible-playbook playbooks/list_images.yml -e server=nodo2

# 2. Exportar la configuración actual del nodo
ansible-playbook playbooks/proxmox_export.yml -e server=nodo2
```

Esto genera archivos como `lxc/lxc-100.yml`, `kvm/vm-101.yml`, etc. en el
`configs_dir` del nodo (ej. `datos-nodo2/`).

### 2. Configurar un nuevo contenedor LXC desde cero

```bash
# 1. Ver qué templates LXC están disponibles
ansible-playbook playbooks/list_images.yml -e server=nodo2

# 2. Crear el archivo de datos (ej. lxc-107.yml)
```

```yaml
# datos-nodo2/lxc/lxc-107.yml
vmid: '107'
type: lxc
config:
  arch: amd64
  cores: '2'
  hostname: web-prueba
  memory: '2048'
  net0: name=eth0,bridge=vmbr0,ip=dhcp,type=veth
  onboot: '1'
  ostype: ubuntu
  swap: '512'
  unprivileged: '1'
  ostemplate: "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
  root_password: "mi-contrasena-segura"
disk_volume:
  storage: main-storage
  size: 30
```

```bash
# 3. Crear el contenedor (apply crea si no existe)
ansible-playbook playbooks/apply_lxc.yml -e server=nodo2 -e id=107
```

El playbook:
- Crea el contenedor LXC con el template y contraseña
- Lo inicia automáticamente
- Obtiene la MAC asignada por Proxmox y la escribe en el YAML

### 3. Agregar un disco más grande y configurar VPN

```bash
# Editar lxc-107.yml: aumentar disk_volume.size a 50 GB
# Luego ejecutar:
ansible-playbook playbooks/apply_lxc.yml -e server=nodo2 -e id=107

# Habilitar TUN/nesting para VPN:
ansible-playbook playbooks/lxc-vpn.yml -e server=nodo2 -e id=107
```

### 4. Configurar una VM KVM desde cero

```yaml
# datos-nodo1/kvm/vm-200.yml
vmid: '200'
type: kvm
config:
  boot: order=scsi0;ide2;net0
  cores: '4'
  memory: '8192'
  name: servidor-prueba
  onboot: '1'
  ostype: l26
  scsihw: virtio-scsi-single
  sockets: '1'
  net0: virtio,bridge=vmbr0
  scsi0: local-lvm:100
  ide2: local:iso/debian-13.2.0-amd64-netinst.iso,media=cdrom
```

```bash
# Crear la VM
ansible-playbook playbooks/apply_vm.yml -e id=200
```

### 5. Eliminar un recurso

```bash
# Eliminar VM
ansible-playbook playbooks/delete-vm.yml -e id=200

# Eliminar LXC
ansible-playbook playbooks/delete-lxc.yml -e id=107
```
