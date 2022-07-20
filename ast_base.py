from dataclasses import dataclass
from lark.tree import Meta

@dataclass
class AST:
    location: Meta

@dataclass
class Exp(AST):
    pass

@dataclass
class Stmt(AST):
    pass

@dataclass
class Decl(AST):
    pass

@dataclass
class Type(AST):
    pass
