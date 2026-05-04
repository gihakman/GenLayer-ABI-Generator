"""CLI for GenLayer ABI Generator."""

import json
import os
import sys
from pathlib import Path

import click

from .parser import extract_abi, abi_to_dict
from .generator import generate_full_ts_package, generate_genlayer_js_wrapper


def _header(text: str) -> str:
    return click.style(text, fg="bright_cyan", bold=True)


def _dim(text: str) -> str:
    return click.style(text, fg="bright_black")


def _ok(text: str) -> str:
    return click.style(text, fg="green")


def _sep() -> str:
    return _dim("-" * 52)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """GenLayer ABI Generator — Type-Safe Frontend Toolkit."""
    pass


@cli.command()
@click.argument("contract_source", type=click.File("r"))
@click.option("--address", default="0x0000...", help="Contract address")
@click.option("--output-dir", "-o", default=".", help="Directory to write generated files")
@click.option("--format", "fmt", type=click.Choice(["json", "ts", "all"]), default="all")
def generate(contract_source, address, output_dir, fmt) -> None:
    """Generate ABI from a GenLayer contract source file."""
    source = contract_source.read()
    contract_source.close()

    abi = extract_abi(source)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []

    if fmt in ("json", "all"):
        json_path = out_path / f"{abi.contract_name}.abi.json"
        with open(json_path, "w") as f:
            json.dump(abi_to_dict(abi), f, indent=2)
        generated.append(json_path)

    if fmt in ("ts", "all"):
        ts_files = generate_full_ts_package(abi, address)
        wrapper = generate_genlayer_js_wrapper(abi, address)

        for filename, content in ts_files.items():
            file_path = out_path / filename
            with open(file_path, "w") as f:
                f.write(content)
            generated.append(file_path)

        wrapper_path = out_path / f"{abi.contract_name}Wrapper.ts"
        with open(wrapper_path, "w") as f:
            f.write(wrapper)
        generated.append(wrapper_path)

    click.echo()
    click.echo(_sep())
    for p in generated:
        click.echo(f"  {_ok('write')} {p}")
    click.echo(_sep())
    click.echo(
        f"  {_dim('contract')}  {abi.contract_name}\n"
        f"  {_dim('methods')}   {len(abi.methods)} extracted\n"
        f"  {_dim('output')}    {out_path.resolve()}"
    )


@cli.command()
@click.argument("contract_source", type=click.File("r"))
@click.option("--pretty", "-p", is_flag=True, default=True, help="Pretty-print output")
def inspect(contract_source, pretty) -> None:
    """Print parsed ABI to stdout."""
    source = contract_source.read()
    contract_source.close()

    abi = extract_abi(source)
    click.echo(_header(abi.contract_name))
    click.echo(f"  {_dim('methods:')} {len(abi.methods)}")
    click.echo()
    indent = 2 if pretty else None
    click.echo(json.dumps(abi_to_dict(abi), indent=indent))


if __name__ == "__main__":
    cli()
