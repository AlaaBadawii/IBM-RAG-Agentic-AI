"""Utility functions for the application."""
import os


def make_dir():
    if os.path.exists("path"):
        print("✓ Path directory already exists.")
    else:
        print("✗ Path directory doesn't exist - creating it...")
        os.makedirs("path")
        print("✓ Path directory created")


def print_stream_info(read, write, _sid, verbose=False):
    """Print information about read/write streams and seeion ID."""
    if verbose:
        print("READ (recives FROM server):")
        print(read)
        print()

        print("WRITE (sends TO server):")
        print(write)
        print()

        print("SEEION ID:")
        print(_sid)

