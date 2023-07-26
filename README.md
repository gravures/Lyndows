# lyndows

A python Wine utility library.

## Usage

A very rough usage example (more will come):

```python
import lyndows.wine as wine
from lyndows.eprocess import EProcess

# Creating a specific execution context for running an exe
# A context gather the wine specific distribution to use 
# within a specified wine prefix and all the environement
# settings needed.
context = wine.WineContext(
    dist="~/MyCustom/winedist",
    prefix="~/MyPrefixes/wine64_01",
    WINEDLLOVERRIDES=[
        "dxvk_config=n",
        "d3d11=n",
        "d3d10=n",
        "d3d10core=n",
        "d3d10_1=n",
        "d3d9=n",
        "dxgi=n"
    ],
    ESYNC=0,
    FSYNC=1,
    LARGE_ADDRESS_AWARE=1
)
wine.WineContext.register(context)

# A special subprocess warper that is cross platform.
# On Windows platform it will skip the leverage of wine
# and just handle the subprocess natively.
exe = EProcess("~/windows/example.exe")
exe.set_arguments(("-info",), ("-option", 3))  # grouping options in tuple (-opt, val)
exe.add_arguments((Path("folder/to/afile.txt"),))  # positional arg (arg,)

# Eprocess.run() works as subprocess.run(), handling all the caveats
# of file path format differences between windows and posix platform
process = exe.run()
if not exe.returncode:
    print(exe.stdout.splitlines())
```
