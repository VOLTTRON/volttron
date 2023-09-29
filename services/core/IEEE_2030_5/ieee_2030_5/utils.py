def is_binary(binary: str) -> bool:
    return all([c in '01' for c in str(binary)])


def is_hex(hex: str) -> bool:
    return all([c in '0123456789ABCDEFabcdef' for c in hex])


def binary_to_binary_hex(binary: str) -> str:
    return hex(int(binary, 2))[2:]


def decimal_to_binary_hex(decimal: int) -> str:
    return hex(int(decimal))[2:]
