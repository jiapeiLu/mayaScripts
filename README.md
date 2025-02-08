# mayaScripts
Some handy scripts, I wrote for myself or my colleague.
# vtxMatch.py
This is a Maya script that can match the vertices of two vertex sets by the nearest distance and can also copy the normals.

[Demo Video](https://youtu.be/J2RodFLoYMM)

Please place the file in the `maya\scripts` folder within the Documents directory.

It requires `numpy`. To install `numpy`, navigate to the Maya application directory (which looks like “C:\Program Files\Autodesk\Maya2023\bin”).

Inside the folder, shift and right-click the mouse. Choose 'Open PowerShell window here', then type:

`shell`
```shell
mayapy.exe -m pip install --user numpy
```

or

```shell
.\mayapy.exe -m pip install --user
```


Maya Usage:

`Python`
```python
import vtxMatch
from importlib import reload
reload(vtxMatch)
```
