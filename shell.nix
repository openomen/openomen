# Development shell for NixOS: Python with PySide6 from nixpkgs, so the GUI
# runs from source without pip wheels (which need libraries NixOS doesn't put
# in /usr/lib). Release binaries are still built with PyInstaller.
#
#   nix-shell --run ./openomen-gui      # run the GUI from the checkout
#   nix-shell --run './openomen stats'  # the CLI works in here too
{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (ps: [ ps.pyside6 ]))
    pkgs.qt6.qtwayland
  ];

  # mkShell doesn't wrap Qt apps, so point Qt at the Wayland platform plugin.
  shellHook = ''
    export QT_PLUGIN_PATH="${pkgs.qt6.qtwayland}/${pkgs.qt6.qtbase.qtPluginPrefix}''${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
  '';
}
