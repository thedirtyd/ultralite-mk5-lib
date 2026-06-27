"""Typed identifiers for device domains (wire indices and catalog keys)."""

from __future__ import annotations

from enum import Enum, IntEnum


class Inputs(IntEnum):
    """Analog input kiGain indices (Mic/Line 1–2, Line 3–8)."""

    MicLineIn01 = 0
    MicLineIn02 = 1
    LineIn03 = 2
    LineIn04 = 3
    LineIn05 = 4
    LineIn06 = 5
    LineIn07 = 6
    LineIn08 = 7


class InputPairs(IntEnum):
    """Stereo pair left gain_ich; writes both L and R crosspoint faders."""

    MicLineIn0102 = 0
    LineIn0304 = 2
    LineIn0506 = 4
    LineIn0708 = 6
    SpdifIn = 8


class Buses(IntEnum):
    """Mix output bus koBusMute / gain_och indices."""

    Main0102 = 0
    Line0304 = 2
    Line0506 = 4
    Line0708 = 6
    Line0910 = 8
    Phones = 10
    Reverb = 12


class Monitors(Enum):
    """Monitor trim section rows (distinct wire property per member)."""

    Main = "main_trim"
    Phones = "output_trim"


class LineOutputs(IntEnum):
    """Line output koTrim trim_index values (OUTPUT_TRIM_CHANNELS order)."""

    MainOut01 = 6
    MainOut02 = 7
    LineOut03 = 8
    LineOut04 = 9
    LineOut05 = 0
    LineOut06 = 1
    LineOut07 = 2
    LineOut08 = 3
    LineOut09 = 4
    LineOut10 = 5


class InputMeters(IntEnum):
    MicLineIn01 = 37
    MicLineIn02 = 32
    LineIn03 = 38
    LineIn04 = 39
    LineIn05 = 35
    LineIn06 = 36
    LineIn07 = 33
    LineIn08 = 34
    SpdifInL = 44
    SpdifInR = 45
    Optical01 = 24
    Optical02 = 25
    Optical03 = 26
    Optical04 = 27
    Optical05 = 28
    Optical06 = 29
    Optical07 = 30
    Optical08 = 31


class MixMeters(IntEnum):
    UsbHostIn01 = 0
    UsbHostIn02 = 1
    MicLineIn01PostFx = 50
    MicLineIn02PostFx = 51
    LineIn03PostFx = 52
    LineIn04PostFx = 53
    LineIn05PostFx = 58
    LineIn06PostFx = 59
    LineIn07PostFx = 60
    LineIn08PostFx = 61
    ReverbWet = 68


class OutputMeters(IntEnum):
    MainOut01Mix = 46
    MainOut02Mix = 47
    LineOut03Mix = 48
    LineOut04Mix = 49
    LineOut05Mix = 54
    LineOut06Mix = 55
    LineOut07Mix = 56
    LineOut08Mix = 57
    LineOut09Mix = 62
    LineOut10Mix = 63
    PhonesMixL = 64
    PhonesMixR = 65
    SpdifOutL = -1
    SpdifOutR = -2
    OpticalOut01 = -10
    OpticalOut02 = -11
    OpticalOut03 = -12
    OpticalOut04 = -13
    OpticalOut05 = -14
    OpticalOut06 = -15
    OpticalOut07 = -16
    OpticalOut08 = -17
