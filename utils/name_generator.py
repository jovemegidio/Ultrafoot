# -*- coding: utf-8 -*-
"""Gerador de nomes brasileiros realistas."""
from __future__ import annotations

import random

PRIMEIROS = [
    "Lucas", "Gabriel", "Rafael", "Matheus", "Bruno", "Felipe",
    "Guilherme", "Pedro", "Vinicius", "Arthur", "Gustavo", "Leonardo",
    "Diego", "Thiago", "Rodrigo", "Andre", "Carlos", "Daniel",
    "Eduardo", "Fernando", "Henrique", "Igor", "João", "Kaique",
    "Leandro", "Marcos", "Nicolas", "Oscar", "Pablo", "Renan",
    "Samuel", "Tales", "Victor", "Wesley", "Yago",
    "Alex", "Cléber", "Deivid", "Élton", "Fábio",
    "Geovane", "Hércules", "Ítalo", "Jadson", "Kléber", "Luisão",
    "Robson", "Adriano", "Juninho", "Denilson", "Emerson",
    "Lúcio", "Juan", "Gilberto", "Raí", "Mauro", "Aldair",
    "Jorginho", "Branco", "Mazinho", "Alemão", "Cerezo", "Falcão",
]

SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa",
    "Rodrigues", "Almeida", "Nascimento", "Lima", "Araújo", "Fernandes",
    "Carvalho", "Gomes", "Martins", "Rocha", "Ribeiro", "Alves",
    "Monteiro", "Mendes", "Barros", "Freitas", "Barbosa", "Pinto",
    "Moura", "Cavalcanti", "Dias", "Castro", "Campos", "Cardoso",
    "Teixeira", "Vieira", "Nunes", "Correia", "Batista", "Moreira",
]


def gerar_nome_brasileiro() -> str:
    """Retorna um nome completo aleatório."""
    return f"{random.choice(PRIMEIROS)} {random.choice(SOBRENOMES)}"
