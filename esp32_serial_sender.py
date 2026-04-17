# pip install pyserial

import time
from typing import List, Optional

import serial
from serial import SerialException
from serial.tools import list_ports


BAUD_RATE = 115200
COMMAND_DELAY_SECONDS = 2
RETRY_DELAY_SECONDS = 3


def get_available_ports() -> List[str]:
    return [port.device for port in list_ports.comports()]


def print_available_ports(ports: List[str]) -> None:
    print("Available COM ports:")
    if not ports:
        print("  No COM ports detected.")
        return

    for index, port in enumerate(ports, start=1):
        print(f"  {index}. {port}")


def choose_port() -> str:
    while True:
        ports = get_available_ports()
        print_available_ports(ports)

        if not ports:
            print(f"No ports found. Retrying in {RETRY_DELAY_SECONDS} seconds...\n")
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        user_input = input(
            "Choose a port by number or type the COM name (example: COM5): "
        ).strip()

        if not user_input:
            print("Please enter a valid selection.\n")
            continue

        if user_input.isdigit():
            selected_index = int(user_input) - 1
            if 0 <= selected_index < len(ports):
                return ports[selected_index]
            print("Invalid port number.\n")
            continue

        normalized_input = user_input.upper()
        for port in ports:
            if port.upper() == normalized_input:
                return port

        print("Port not found. Refreshing list...\n")
        time.sleep(1)


def open_serial_connection(port_name: str) -> Optional[serial.Serial]:
    while True:
        ports = get_available_ports()
        if port_name not in ports:
            print(f"Port {port_name} not found. Retrying in {RETRY_DELAY_SECONDS} seconds...")
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        try:
            print(f"Connecting to {port_name} at {BAUD_RATE} baud...")
            connection = serial.Serial(port=port_name, baudrate=BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"Connected to {port_name}\n")
            return connection
        except SerialException as error:
            error_message = str(error).lower()

            if "access is denied" in error_message or "permissionerror" in error_message:
                print(f"Port busy: {port_name} is already in use. Close Serial Monitor or other apps and try again.")
                return None

            print(f"Could not open {port_name}: {error}")
            print(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
            time.sleep(RETRY_DELAY_SECONDS)


def send_command(connection: serial.Serial, command: str, label: str) -> None:
    print(label)
    connection.write(command.encode("ascii"))
    connection.flush()


def run_sender_loop(connection: serial.Serial) -> None:
    while True:
        send_command(connection, "1", "Sending ON")
        time.sleep(COMMAND_DELAY_SECONDS)

        send_command(connection, "0", "Sending OFF")
        time.sleep(COMMAND_DELAY_SECONDS)


def main() -> None:
    port_name = choose_port()
    connection = open_serial_connection(port_name)

    if connection is None:
        return

    try:
        run_sender_loop(connection)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except SerialException as error:
        print(f"\nSerial communication error: {error}")
    finally:
        if connection.is_open:
            connection.close()
            print("Serial port closed.")


if __name__ == "__main__":
    main()
