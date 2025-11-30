import os
import shutil
import textwrap
from enum import IntFlag, auto
from pathlib import Path

from conan import ConanFile
from conan.tools.files import get, rmdir


class NuGetRecipe(ConanFile):
    def source(self):
        version = os.getenv("CCACHE_VERSION")
        assert version is not None, "CCACHE_VERSION environment variable is not set"
        url = f"https://github.com/ccache/ccache/releases/download/v{version}/ccache-{version}-windows-x86_64.zip"

        REPO_FOLDER = Path(__file__).parent

        folders = [
            TEMP_FOLDER := REPO_FOLDER / "package_",
            PACKAGE_FOLDER := REPO_FOLDER / "package",
            PACKAGES_FOLDER := REPO_FOLDER / "packages",
            INSTALLS_FOLDER := REPO_FOLDER / "installs",
        ]

        for folder in folders:
            rmdir(self, folder)

        nuget = shutil.which("nuget")
        assert nuget is not None, "nuget executable not found in PATH"

        def run_test(folder: Path) -> None:
            exe_path = folder / "tools" / "ccache.exe"
            self.run(f'"{exe_path}" --version')

        def get_source_and_prepare() -> None:
            assert self.conan_data is not None
            sha256 = self.conan_data["sources"][version]["sha256"]
            get(self, url, strip_root=True, destination=TEMP_FOLDER.name, sha256=sha256)

            coverage = FullCoverage(TEMP_FOLDER, verbose=True)
            coverage.include("ccache.exe", target="tools")
            coverage.include("*.html", target="docs")
            coverage.exclude("*.adoc")
            coverage.validate()

            for file, target in coverage.get_includes_with_targets().items():
                target_path = PACKAGE_FOLDER / target
                target_path.mkdir(parents=True, exist_ok=True)
                print("Moving file {} to {}".format(file, target_path / file.name))
                file.rename(target_path / file.name)

            shutil.copy(Path(REPO_FOLDER / "README.md"), PACKAGE_FOLDER)
            run_test(PACKAGE_FOLDER)

        def pack_nupkg() -> None:
            # Pack .nupkg
            self.run(
                f'"{nuget}" pack ccache.nuspec -Version {version} -OutputDirectory "{PACKAGES_FOLDER}"'
            )
            # Try to install it using nuget.
            # `NoHttpCache` is required, otherwise it might install from local cache instead of the provided source.
            # Which can occur when rebuilding the package muiltiple times.
            self.run(
                f'"{nuget}" install ccache -Version {version}'
                f' -Source "{PACKAGES_FOLDER}" -OutputDirectory "{INSTALLS_FOLDER}"'
                " -NoHttpCache"
            )
            install_folder = INSTALLS_FOLDER / f"ccache.{version}"
            assert install_folder.exists(), install_folder
            run_test(install_folder)

        get_source_and_prepare()
        pack_nupkg()

        # In theory we can upload .nupkg here as a workflow artifact.
        # We can also upload it to dev.nugettest.org, so it can be tested locally
        # with `nuget install .. -Source https://dev.nugettest.org/api/v2/`.
        msg = f"""\
            It's recommended to first push to dev.nugettest.org to verify everything is fine.
                [DEV]    nuget push packages/ccache.{version}.nupkg -Source https://dev.nugettest.org/api/v2/package"
                [DEV]    nuget install ccache -Version {version} -Source https://dev.nugettest.org/api/v2/

            Run commands below to push the package to nuget.org:
                [MAIN]   nuget push packages/ccache.{version}.nupkg -Source https://api.nuget.org/v3/index.json
                [MAIN]   nuget install ccache -Version {version}
            """
        print(textwrap.dedent(msg))


class FullCoverageStatus(IntFlag):
    INCLUDED = auto()
    EXCLUDED = auto()


class FullCoverage:
    def __init__(self, path: Path, *, verbose: bool = False) -> None:
        self.path = path
        self.files: dict[Path, FullCoverageStatus] = {
            file: FullCoverageStatus(0) for file in self.path.rglob("*")
        }
        self.targets: dict[Path, str] = {}
        self.verbose = verbose
        if self.verbose:
            print(f"Adding files from path {self.path}:")
            for file in self.files:
                print(f" - {file}")

    def _apply_status(self, flag: FullCoverageStatus, pattern: str) -> list[Path]:
        files = list(self.path.glob(pattern))
        for file in files:
            self.files[file] |= flag

        if self.verbose:
            action = "Including" if flag == FullCoverageStatus.INCLUDED else "Excluding"
            print(f"{action} files matching pattern '{pattern}':")
            for file in files:
                print(f" - {file}")
        return files

    def include(self, pattern: str, target: str = ".") -> None:
        flag = FullCoverageStatus["INCLUDED"]
        files = self._apply_status(flag, pattern)

        for file in files:
            self.targets[file] = target

    def exclude(self, pattern: str) -> None:
        flag = FullCoverageStatus["EXCLUDED"]
        self._apply_status(flag, pattern)

    def validate(self) -> None:
        uncovered_files = [
            file
            for file, status in self.files.items()
            if status == FullCoverageStatus(0)
        ]
        if not uncovered_files:
            if self.verbose:
                print(f"All files in path '{self.path}' are covered:")
                for file, status in self.files.items():
                    print(f" - {file}: {status!r}")
            return
        message = (
            f"\nDetected uncovered files in path '{self.path}'! See the list below.\n"
        )
        message += "\n".join(f"- {file}" for file in uncovered_files)
        raise Exception(message)

    def get_includes_with_targets(self) -> dict[Path, str]:
        return self.targets

    def get_excluded_paths(self) -> list[Path]:
        return [
            file
            for file, status in self.files.items()
            if status & FullCoverageStatus.EXCLUDED
        ]
