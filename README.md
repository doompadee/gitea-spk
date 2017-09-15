# gitea-spk

Fork from [gogs-spk](https://github.com/alexandregz/gogs-spk) to create a SPK package for [Gitea](https://github.com/go-gitea/gitea), a [Gogs](https://gogs.io/) fork.

### Dependencies

The Gitea package requires the **[Git Server](https://www.synology.com/en-global/dsm/packages/Git)** package.

### Package creation

To create the package, clone the repository:

`$ git clone https://github.com/flipswitchingmonkey/gitea-spk.git`

Change into the newly created directory - the root directory:

`$ cd gitea-spk`

Invoke the build script to have the most recent Gitea release downloaded and
the install package created. The build script requires Python 2.7 (the current
DiskStation default).

`$ ./create_spk.py`

The install package matching your DiskStation will be created in the root
directory.

When building not directly on a DiskStation, you have to specify the package
arch matching your DiskStation. If you don't know the matching package arch,
login via ssh and display system information:

`$ uname -a`

This will reveal the Synology model as well as the used architecture, e.g.
"synology_braswell_ds716+".

`$ ./create_spk.py -a braswell`

You can also manually download Gitea binaries and specify the binary for which
the package should be created:

`$ ./create_spk.py gitea-1.1.3-linux-arm-7`

### Installation

Make sure **Package Center > Settings > General > Trust Level** is set to **Any Publisher** and perform installation via **Package Center > Manual Install**.

![Select Package](screenshots/install_select_package.png)

The installer will create the (internal) user/group gitea:gitea when not found and the executable is run with this user.

![Select Package](screenshots/install_running.png)

When installation has finished, the package center shows url and status of your Gitea server.

When accessed for the first time, Gitea will greet you with the installation settings. You should set your **Repository Root Path** to a shared folder. You can configure permissions for shared folders in the control panel via **Edit > Permissions > System internal user** to grant the Gitea user permission.

Tested to work on DS116 with Gitea 1.0.1.

### Acknowledgements

Original code copyright (c) 2016 Alexandre Espinosa Menor
