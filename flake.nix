{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {inherit system;};
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            (pkgs.python3.withPackages (ps:
              with ps; [
                fastapi
                uvicorn
                confluent-kafka
                httpx
              ]))
          ];

          shellHook = ''
            export SHELL=${pkgs.bashInteractive}/bin/bash
            echo "Python: $(python --version) (with FastAPI included)"
          '';
        };
      }
    );
}
