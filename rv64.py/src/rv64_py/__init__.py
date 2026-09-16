from enum import Enum
from collections.abc import Callable
from ctypes import byref, CDLL, c_int, c_size_t, c_void_p, POINTER
from ctypes.util import find_library

import resource

import numpy as np
import numpy.typing as npt


# you know, I'm starting to think it might've been easier to just write this in C or Zig...
# out here writing my own memory allocator in PYTHON of all languages
class Allocator:
    def __init__(self):
        libc = CDLL(find_library("c"))
        libc.posix_memalign.argtypes = [POINTER(c_void_p), c_size_t, c_size_t]
        libc.posix_memalign.restype = c_int

        self.libc = libc
        self.page_size = c_size_t(resource.getpagesize())

        self.pages = list[c_void_p]

    def _new_page(self, size: c_size_t) -> c_void_p:
        """
        Allocate a region of memory
        """

        ptr = c_void_p()
        result = self.libc.posix_memalign(byref(ptr), self.page_size, size)
        if result != 0:
            for page in self.pages:
                self.libc.free(page)
            raise MemoryError(f"Failed to allocate memory: {result}")

        return ptr


class Register(Enum):
    zero = 0  # zero (writes ignored)
    ra = 1  # return address
    sp = 2  # stack pointer
    gp = 3  # global pointer
    tp = 4  # thread pointer

    t0 = 5  # temporary register
    t1 = 6
    t2 = 7

    fp = 8  # frame pointer
    s0 = fp  # saved register
    s1 = 9

    a0 = 10  # function arguments and return values
    a1 = 11
    a2 = 12  # function arguments
    a3 = 13
    a4 = 14
    a5 = 15
    a6 = 16
    a7 = 17

    s2 = 18  # saved registers
    s3 = 19
    s4 = 20
    s5 = 21
    s6 = 22
    s7 = 23
    s8 = 24
    s9 = 25
    s10 = 26
    s11 = 27

    t3 = 28
    t4 = 29
    t5 = 30
    t6 = 31

    ft0 = 32  # fp temporaries
    ft1 = 33
    ft2 = 34
    ft3 = 35
    ft4 = 36
    ft5 = 37
    ft6 = 38
    ft7 = 39

    fs0 = 40  # fp saved registers
    fs1 = 41

    fa0 = 42  # fp return values and arguments
    fa1 = 43
    fa2 = 44  # arguments
    fa3 = 45
    fa4 = 46
    fa5 = 47
    fa6 = 48
    fa7 = 49

    fs2 = 50  # fp saved registers
    fs3 = 51
    fs4 = 52
    fs5 = 53
    fs6 = 54
    fs7 = 55
    fs8 = 56
    fs9 = 57
    fs10 = 58
    fs11 = 59

    ft8 = 60  # temporary registers
    ft9 = 61
    ft10 = 62
    ft11 = 63


# Note to self: *W instructions ignore upper 32 bits and sign extend to 64b


class VirtualMachine:
    registers = np.array(64, np.uint64)
    memory = np.array(4 * 1024 * 1024, np.uint64)
    pc = np.uint64(0)

    def __init__(self):
        self.opcodes: tuple[Callable[[np.uint32], None]] = (
            self._load,  # 0b00000_11
            # 0b00001_11: float32 load operations
            self._raise(NotImplementedError()),
            # 0b00010_11: custom-0
            self._raise(ValueError("Invalid opcode: custom-0 (0001011) not supported")),
            # 0b00011_11: Memory/IO fencing
            self._raise(NotImplementedError()),
            self._integer_register_immediate,  # 0b00100_11
            self._auipc,  # 0b00101_11
            self._integer_register_immediate32,  # 0b00110_11
            # 0b00111_11: 48-bit instruction
            self._raise(NotImplementedError("Found 48-bit instruction")),
            self._store,  # 0b01000_11
            # 0b01001_11: float32 store operations
            self._raise(NotImplementedError()),
            # 0b01010_11: custom-1
            self._raise(ValueError("Invalid opcode: custom-1 (0101011) not supported")),
            # 0b01011_11: Atomic memory extension
            self._raise(NotImplementedError()),
            self._integer_register_register,  # 0b01100_11
            self._lui,  # 0b01101_11
            self._integer_register_register32,  # 0b01110_11
            # 0b01111_11: 64-bit instruction
            self._raise(NotImplementedError("Found 64-bit instruction")),
            # 0b10000_11: floating point multiply add
            self._raise(NotImplementedError()),
            # 0b10001_11: floating point multiply subtract
            self._raise(NotImplementedError()),
            # 0b10010_11: fused negate multiply subtract
            self._raise(NotImplementedError()),
            # 0b10011_11: fused negate multiply add
            self._raise(NotImplementedError()),
            # 0b10100_11: floating point ops
            self._raise(NotImplementedError()),
            # 0b10101_11: reserved
            self._raise(ValueError("Invalid opcode 1010111 (reserved) not supported")),
            # 0b10110_11: custom-2 or rv128
            self._raise(
                ValueError("Invalid opcode 1011011 (custom-2 or RV128) not supported")
            ),
            # 0b10111_11: 48-bit instruction: the sequel
            self._raise(NotImplementedError("Found 48-bit instruction")),
            self._branch,  # 0b11000_11
            self._jalr,  # 0b11001_11
            # 0b11010_11: Vector
            self._raise(
                ValueError("Invalid opcode 0b1101011 (reserved) not supported")
            ),
            # 0b11011_11: Jump and link
            self._jal,  # 0b11011_11
            # 0b11100_11: SYSTEM?
            self._raise(NotImplementedError()),
            # 0b11101_11: reserved
            self._raise(
                ValueError("Invalid opcode: 0b1110111 (reserved) not supported")
            ),
            # 0b11110_11: custom-3 or RV128
            self._raise(
                ValueError(
                    "Invalid opcode 0b1111011 (custom-3 or RV128) not implemented"
                )
            ),
            # 0b11111_11: Instruction width >= 80b
            self._raise(NotImplementedError("Found 80+ bit instruction")),
        )

    def _raise(self, e: Exception) -> Callable[..., None]:
        def placeholder(*args):
            raise e

        return placeholder

    # opcode 0000011
    def _load(self, inst: np.uint32) -> None:
        """
        Integer load

        Instruction Format
        000000000000	00000	000		00000	0000011
        offset			base	width	dest	opcode
        """

        # TODO
        raise NotImplementedError("VM Memory not yet fully implemented")

        # opcode	= inst & 0x7F
        # rd		= (inst >> 7) & 0x1F
        # if rd == 0:
        # return
        # width	= (inst >> 12) & 0x7
        # base	= (inst >> 15) & 0x1F

        # imms	= np.int32(inst) >> 20
        # imm		= np.uint64(np.int64(imms))	# TODO: view instead?

        # addr = self.registers[base] + imm

        # TODO: actually implement memory mapping
        # self.registers[dest] = self.all_memory[addr]

    # opcode 0010011
    def _integer_register_immediate(self, inst: np.uint32) -> None:
        """
        Integer Register-Immediate Instructions

        Arithmetic Format
        000000000000	00000	000		00000	0010011
        immediate		src		funct3	dest	opcode

        Logical Format
        000000	000000	00000	000		00000	0010011
        funct6	shamt	src		funct3	dest	opcode
        """

        # opcode	= inst & 0x7F
        rd = (inst >> 7) & 0x1F
        if rd == 0:
            return
        funct3 = (inst >> 12) & 0x7
        rs1 = (inst >> 15) & 0x1F

        imms = np.int32(inst) >> 20
        imm = np.uint64(np.int64(imms))  # TODO: view instead?

        src = self.registers[rs1]

        match funct3:
            case 0b000:  # ADDI
                self.registers[rd] = src + imm
            case 0b001:  # SLLI
                if inst >> 26:
                    funct6 = inst >> 26
                    raise ValueError(
                        "Illegal instruction: opcode 0b0010011 with funct3 0b001 only supports"
                        f" funct6 0b000000 ({funct6:#0{8}b} found)"
                    )
                self.registers[rd] = src << (imm & 0x3F)
            case 0b010:  # SLTI
                self.registers[rd] = np.uint64(
                    1 if src.view(np.int64) < np.int64(imm) else 0
                )
            case 0b011:  # SLTIU
                self.registers[rd] = np.uint64(1 if src < np.uint64(imm) else 0)
            case 0b100:  # XORI
                self.registers[rd] = src ^ np.uint64(imm)
            case 0b101:  # SRLI/SRAI
                shamt = imm & 0x3F
                funct6 = inst >> 26
                if funct6 == 0b010000:  # SRAI
                    self.registers[rd] = np.right_shift(src.view(np.int64), shamt).view(
                        np.uint64
                    )
                elif funct6 == 0:  # SRLI
                    self.registers[rd] = src >> shamt
                else:
                    raise ValueError(
                        "Illegal instruction: opcode 0b0010011 with funct3 0b101 only supports"
                        f" funct6 0b000000 and funct6 0b010000 ({funct6:#0{8}b} found)"
                    )
            case 0b110:  # ORI
                self.registers[rd] = src | np.uint64(imm)
            case 0b111:  # ANDI
                self.registers[rd] = src & np.uint64(imm)

    # opcode 0010111
    def _auipc(self, inst: np.uint32) -> None:
        """
        Add Upper Immediate to Program Counter

        Instruction Format
        00000000000000000000	00000	0010111
        immediate				rd		opcode
        """

        # opcode	= inst & 0x7F
        rd = (inst >> 7) & 0x1F
        if rd == 0:
            return

        self.registers[rd] = self.pc + (inst & 0xFFFFF000)

    # opcode 0011011
    def _integer_register_immediate32(self, inst: np.uint32) -> None:
        """
        Integer Register-Immediate 32-bit instructions

        Arithmetic Format
        000000000000	00000	000		00000	0000000
        immediate		src		funct3	dest	opcode
        """

        # opcode	= inst & 0x7F
        rd = (inst >> 7) & 0x1F
        if rd == 0:
            return
        funct3 = (inst >> 12) & 0x7
        rs1 = (inst >> 15) & 0x1F

        imm = np.int32(inst) >> 20

        src = np.uint32(self.registers[rs1] & 0xFFFFFFFF)

        match funct3:
            case 0b000:  # ADDIW
                self.registers[rd] = np.int64(np.int32(src + imm)).view(np.uint64)
            case 0b001:  # SLLIW
                if inst >> 26:
                    funct6 = inst >> 26
                    raise ValueError(
                        "Illegal instruction: opcode 0b0011011 with funct3 0b001 only supports"
                        f" funct6 0b000000 ({funct6:#0{8}b} found)"
                    )
                if inst & 0x1000000:
                    raise ValueError(
                        "Illegal instruction: opcode 0b0011011 with funct3 0b001 bit 25 must be 0"
                        " (found 1)"
                    )
                self.registers[rd] = np.int64(np.int32(src << (imm & 0x1F))).view(
                    np.uint64
                )
            case 0b101:  # SRLIW/SRAIW
                shamt = imm & 0x1F
                if imm & 0x20:
                    raise ValueError(
                        "Illegal instruction: opcode 0b0011011 bit 24 (imm[5]) must be 0 (1 found)"
                    )
                funct6 = inst >> 26
                if funct6 == 0b010000:  # SRAIW
                    self.registers[rd] = np.int64(
                        np.right_shift(src.view(np.int32), shamt).view(np.uint32)
                    ).view(np.uint64)
                elif funct6 == 0:  # SRLIW
                    self.registers[rd] = np.int64(np.int32(src >> shamt)).view(
                        np.uint64
                    )
                else:
                    raise ValueError(
                        "Illegal instruction: opcode 0b0011011 with funct3 0b101 only supports"
                        f" funct6 0b000000 and funct6 0b010000 ({funct6:#0{8}b} found)"
                    )
            case _:
                raise ValueError(
                    "Illegal instruction: opcode 0b0011011 only supports funct3 0b000, 0b001, and"
                    f" 0b101 ({funct3:#{5}b} found)"
                )

    # opcode 0100011
    def _store(self, inst: np.uint32) -> None:
        """
        Integer Store Instructions

        Instruction Format
        0000000		00000	00000	000		00000	0100011
        offset		src		base	width	offset	opcode
        """

        raise NotImplementedError("Integer store ops not yet fully implemented")

        # opcode	= inst & 0x7F
        # offset5	= (inst >> 7) & 0x1F
        # width	= (inst >> 12) & 0x7
        # base	= (inst >> 15) & 0x1F
        # src		= (inst >> 20) & 0x1F
        # offset7	= (inst >> 25) & 0x7F

        # offset = (offset7 << 5) | offset5

        # data = self.registers[src]
        # addr = self.registers[base] + offset

        # match width:
        # case 0b000:	# sb
        # self.all_memory[addr] = data & 0xFF
        # case 0b001:	# sh
        # self.all_memory[addr] = data & 0xFFFF
        # case 0b010:	# sw
        # self.all_memory[addr] = data & 0xFFFFFFFF
        # case 0b100:	# sd
        # self.all_memory[addr] = data
        # case _:
        # raise ValueError(
        # "Illegal instruction: opcode 0b0100011 only supports funct3 0b000-0b100"
        # f" ({funct3:#{5}b} found)"
        # )

    # opcode 0110011
    def _integer_register_register(self, inst: np.uint32) -> None:
        """
        Integer Register-Register Instructions

        Instruction Format
        0000000		00000	00000	000		00000	0110011
        funct7		rs2		rs1		funct3	rd		opcode
        """

        # opcode	= inst & 0x7f
        rd = (inst >> 7) & 0x1F
        if rd == 0:
            return
        funct3 = (inst >> 12) & 0x7
        rs1 = (inst >> 15) & 0x1F
        rs2 = (inst >> 20) & 0x1F
        funct7 = (
            inst >> 25
        ) & 0x7F  # 0100000 = Subtract	0000000 = Add		for funct3=0b000
        # 0100000 = Arithmetic	0000000 = Logical	for funct3=0b101

        src1 = self.registers[rs1]
        src2 = self.registers[rs2]
        try:
            match funct3:
                case 0b000:  # ADD/SUB
                    if funct7 == 0b0000000:  # ADD
                        self.registers[rd] = src1 + src2
                    elif funct7 == 0b0100000:  # SUB
                        self.registers[rd] = src1 - src2
                    else:
                        raise ValueError
                case 0b001:  # SLL
                    if funct7:
                        raise ValueError
                    self.registers[rd] = src1 << (src2 & 0x3F)
                case 0b010:  # SLT
                    if funct7:
                        raise ValueError
                    self.registers[rd] = np.uint64(
                        1 if np.int64(src1) < np.int64(src2) else 0
                    )
                case 0b011:  # SLTU
                    if funct7:
                        raise ValueError
                    self.registers[rd] = np.uint64(1 if src1 < src2 else 0)
                case 0b100:  # XOR
                    if funct7:
                        raise ValueError
                    self.registers[rd] = src1 ^ src2
                case 0b101:  # SRL/SRA
                    if funct7 == 0b0000000:  # SRL
                        self.registers[rd] = src1 >> (src2 & 0x3F)
                    elif funct7 == 0b0100000:  # SRA
                        self.registers[rd] = np.right_shift(
                            src1.view(np.int64), (src2 & 0x3F)
                        ).view(np.uint64)
                    else:
                        raise ValueError
                case 0b110:  # OR
                    if funct7:
                        raise ValueError
                    self.registers[rd] = src1 | src2
                case 0b111:  # AND
                    if funct7:
                        raise ValueError
                    self.registers[rd] = src1 & src2
        except ValueError:
            raise ValueError(
                "Illegal instruction: opcode 0b0110011 only supports funct7 0b0000000 or 0b0100000"
                f" ({funct7:#0{9}b} found)"
            )

    # opcode 0110111
    def _lui(self, inst: np.uint32) -> None:
        """
        Load Upper Immediate Instruction

        Instruction Format
        00000000000000000000	00000	0110111
        immediate				rd		opcode
        """

        # opcode	= inst & 0x7F
        rd = (inst >> 7) & 0x1F
        if rd == 0:
            return

        imms = np.int32(inst) >> 12
        imm = np.uint64(np.int64(imms))

        self.registers[rd] = imm

    # opcode 0111011
    def _integer_register_register32(self, inst: np.uint32) -> None:
        """
        32-bit Integer Register-Register Instructions

        Instruction Format
        0000000		00000	00000	000		00000	0111011
        funct7		rs2		rs1		funct3	rd		opcode
        """

        # opcode	= inst & 0x7f
        rd = (inst >> 7) & 0x1F
        if rd == 0:
            return
        funct3 = (inst >> 12) & 0x7
        rs1 = (inst >> 15) & 0x1F
        rs2 = (inst >> 20) & 0x1F
        funct7 = (
            inst >> 25
        ) & 0x7F  # 0100000 = Subtract	0000000 = Add		for funct3=0b000
        # 0100000 = Arithmetic	0000000 = Logical	for funct3=0b101

        src1 = np.uint32(self.registers[rs1] & 0xFFFFFFFF)
        src2 = np.uint32(self.registers[rs2] & 0xFFFFFFFF)
        try:
            match funct3:
                case 0b000:  # ADDW/SUBW
                    if funct7 == 0b0000000:  # ADDW
                        self.registers[rd] = np.int64(np.int32(src1 + src2)).view(
                            np.uint64
                        )
                    elif funct7 == 0b0100000:  # SUBW
                        self.registers[rd] = np.int64(np.int32(src1 - src2)).view(
                            np.uint64
                        )
                    else:
                        raise ValueError
                case 0b001:  # SLLW
                    if funct7:
                        raise ValueError
                    self.registers[rd] = np.int64(np.int32(src1 << (src2 & 0x1F))).view(
                        np.uint64
                    )
                case 0b101:  # SRLW/SRAW
                    shamt = src2 & 0x1F
                    if funct7 == 0b0000000:  # SRLW
                        self.registers[rd] = np.int64(np.int32(src1 >> shamt)).view(
                            np.uint64
                        )
                    elif funct7 == 0b0100000:  # SRAW
                        self.registers[rd] = np.int64(
                            np.right_shift(src1.view(np.int32), shamt)
                        ).view(np.uint64)
                    else:
                        raise ValueError
                case _:
                    raise ValueError
        except ValueError:
            raise ValueError(
                "Illegal instruction: opcode 0b0111011 only supports"
                f" funct7 0b0000000 or 0b0100000 ({funct7:#0{9}b} found) and"
                f" funct3 0b000, 0b001, and 0b101 ({funct3:#0{5}b} found)"
            )

    # opcode 1100011
    def _branch(self, inst: np.uint32) -> None:
        """
        Branch Instructions
        """

        raise NotImplementedError

    # opcode 1100111
    def _jalr(self, inst: np.uint32) -> None:
        """
        Jump and Link Register Instructions
        """

        raise NotImplementedError

    # opcode 1101111
    def _jal(self, inst: np.uint32) -> None:
        """
        Jump and Link Instructions
        """

        raise NotImplementedError

    def load_program(self, program: npt.NDArray[np.uint32]) -> None:
        self.program = program

    def run(self) -> None:
        if not self.program:
            raise Exception("No program loaded")
        for inst in self.program:
            if inst & 0x3 != 3:
                raise NotImplementedError("Compressed instruction found")
            opcode_idx = inst >> 2 & 0x1F
            self.opcodes[opcode_idx](inst)
