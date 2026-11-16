"""A positive integer is 'magic' here when its repeated digit sum is 1.

In CodePilot's Compiler, run this code, then send 1729 in the Live Console.
"""


def is_magic_number(number: int) -> bool:
    if number <= 0:
        return False
    while number >= 10:
        number = sum(int(digit) for digit in str(number))
    return number == 1


if __name__ == "__main__":
    try:
        number = int(input("Enter a positive integer: "))
        if number <= 0:
            print("Please enter a positive integer.")
        elif is_magic_number(number):
            print(f"{number} is a magic number.")
        else:
            print(f"{number} is not a magic number.")
    except ValueError:
        print("Invalid input. Please enter an integer.")
    except EOFError:
        print("No input received. Run again and send a number in the Live Console.")
