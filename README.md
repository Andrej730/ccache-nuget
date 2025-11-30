### NuGet ccache package

| Repository / Package       | URL | Badge |
|----------------------------|-----|----------------|
| Original repository        | https://github.com/ccache/ccache/ | [![Latest tag](https://img.shields.io/github/v/tag/ccache/ccache?sort=semver)](https://github.com/ccache/ccache/) |
| NuGet package              | https://nuget.org/packages/ccache/ | [![NuGet version](https://img.shields.io/nuget/v/ccache)](https://nuget.org/packages/ccache/) |
| ccache-nuget               | https://github.com/Andrej730/ccache-nuget | - |

---

NuGet package building from PowerShell:
```sh
uv sync
.venv\Scripts\activate

# ccache version to package.
$env:CCACHE_VERSION="4.12.2"
# Follow printed instructions after to upload the package to nuget.org
poe build

# Clean up.
poe clean
```


Folders layout:
- `package_` - temporary folder for building the package
- `package` - already structured package folder, ready to be packed
- `packages` - output folder for .nupkg files
- `installs` - folder with .nupkg installed to verify the end-user view of the package
