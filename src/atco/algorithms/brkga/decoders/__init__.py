"""Decoders del BRKGA."""

from atco.algorithms.brkga.decoders.base import DecoderBase
from atco.algorithms.brkga.decoders.permutations import PermutationDecoder

__all__ = ["DecoderBase", "PermutationDecoder"]
