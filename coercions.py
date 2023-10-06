from ast_base import *
from ast_types import *
from values import Box
from tuple_value import TupleValue
from variant_value import Variant

@dataclass(frozen=True)
class Coercion:
    location: Meta

    def source_type(self) -> Type:
        raise Exception('Coercion.source_type method unimplemented')

    def target_type(self) -> Type:
        raise Exception('Coercion.target_type method unimplemented')

    def apply(self, val: Value) -> Value:
        raise Exception('Coercion.apply method unimplemented')


@dataclass(frozen=True)
class Inject(Coercion):
    source: Type

    def source_type(self) -> Type:
        return self.source

    def target_type(self) -> Type:
        return AnyType(self.location)

    def apply(self, val: Value) -> Value:
        return Box(val, self.source)

    def __str__(self):
        return str(self.source) + "!"

@dataclass(frozen=True)
class Project(Coercion):
    target: Type

    def source_type(self) -> Type:
        return AnyType(self.location)

    def target_type(self) -> Type:
        return self.target

    def apply(self, val: Value) -> Value:
        match val:
            case Box(v, source):
                if source == self.target:
                    return v
                else:
                    raise Exception('projection failed, ' + str(val) + ' not of type ' + str(self.target))
            case _:
                raise Exception('projection failed, ' + str(val) + ' not boxed')

    def __str__(self):
        return str(self.target) + "?"

@dataclass(frozen=True)
class CoerceTuple(Coercion):
    elt_coercions: list[Coercion]

    def source_type(self) -> Type:
        return TupleType(self.location, [c.source_type() for c in self.elt_coercions])

    def target_type(self) -> Type:
        return TupleType(self.location, [c.target_type() for c in self.elt_coercions])

    def __str__(self):
        return "⟨" + ', '.join([str(c) for c in self.elt_coercions]) + "⟩"
    
    def __repr__(self):
        return str(self)

    def apply(self, val: Value) -> Value:
        vs = [c.apply(elt) for elt,c in zip(val.elts, self.elt_coercions)]
        return TupleValue(vs)
    
@dataclass(frozen=True)
class CoerceFunction(Coercion):
    params: list[Coercion]
    ret: Coercion

    def source_type(self) -> Type:
        return FunctionType(self.location, [],
                            [c.target_type() for c in self.params], self.ret.source_type(),
                            [])

    def target_type(self) -> Type:
        return FunctionType(self.location, [],
                            [c.source_type() for c in self.params], self.ret.target_type(), [])

@dataclass
class Proxy(Value):
    value: Value
    coercion: Coercion

    def __str__(self):
        return '⟪' + str(self.coercion) + '⟫' + str(self.value)
    
    def read(self, memory, loc):
        match self.coercion:
          case CoercePointer(l, rd, wr):
            return rd.apply(self.value.read(memory, loc))
          case _:
            error(loc, 'Proxy.read coercion not CoercePointer'
                  + str(self.coercion))

    def get_permission(self):
        return self.value.get_permission()
            
    def duplicate(self, percentage, location):
        return Proxy(self.value.duplicate(percentage, location),
                     self.coercion)
    
    def kill(self, mem, location, progress=set()):
        self.value.kill(mem, location, progress)

@dataclass(frozen=True)
class CoercePointer(Coercion):
    read: Coercion
    write: Coercion

    def __str__(self):
        return 'Ref(' + str(self.read) + ', ' + str(self.write) + ')'
    
    def __repr__(self):
        return str(self)
    
    def source_type(self) -> Type:
        return PointerType(self.location, self.read.source_type())

    def target_type(self) -> Type:
        return PointerType(self.location, self.read.target_type())

    def apply(self, val: Value) -> Value:
        return Proxy(val, self)

@dataclass(frozen=True)
class CoerceArray(Coercion):
    read: Coercion
    write: Coercion

    def source_type(self) -> Type:
        return ArrayType(self.location, self.read.source_type())

    def target_type(self) -> Type:
        return ArrayType(self.location, self.read.target_type())


@dataclass(frozen=True)
class IdCoercion(Coercion):
    typ: Type

    def source_type(self) -> Type:
        return self.typ

    def target_type(self) -> Type:
        return self.typ

    def apply(self, val: Value) -> Value:
        return val

    def __str__(self):
        return 'id'

@dataclass(frozen=True)
class Compose(Coercion):
    first : Coercion
    second : Coercion
    def source_type(self) -> Type:
        return self.first.source_type()
    def target_type(self) -> Type:
        return self.second.target_type()
    def apply(self, val: Value) -> Value:
        return self.second.apply(self.first.apply(val))
    def __str__(self):
        return str(self.first) + ";" + str(self.second)
    def __repr__(self):
        return str(self)
    
@dataclass(frozen=True)
class CoerceRecord(Coercion):
    elt_coercions: dict[str, Coercion]

    def source_type(self) -> Type:
        return RecordType(tuple((f, c.source_type()) for (f, c) in self.elt_coercions.items()))

    def target_type(self) -> Type:
        return RecordType(tuple((f, c.target_type()) for (f, c) in self.elt_coercions.items()))

    def apply(self, val: Value) -> Value:
        fs = {f: self.elt_coercions[f].apply(v) for f,v in val.fields.items() }
        return Record(fs)

@dataclass(frozen=True)
class CoerceVariant(Coercion):
    elt_coercions: dict[str, Coercion]

    def __str__(self):
        return '⦅' + ', '.join([f + ':' + str(c)
                                for f,c in self.elt_coercions.items()]) + '⦆'

    def source_type(self) -> Type:
        return VariantType(tuple((f, c.source_type()) for (f, c) in self.elt_coercions.items()))

    def target_type(self) -> Type:
        return VariantType(tuple((f, c.target_type()) for (f, c) in self.elt_coercions.items()))

    def apply(self, val: Value) -> Value:
        match val:
          case Variant(tag, val):
            return Variant(tag, self.elt_coercions[tag].apply(val))
          case _:
            error(self.location,
                  "in CoerceVariant, expected a variant, not " + str(val))

def make_coercion(source: Type, target: Type, loc: Meta) -> Coercion:
    match (source, target):
        case (AnyType(), _) if target.is_ground():
            return Project(loc, target)
        case (AnyType(), TupleType(ts)):
            any_types = [AnyType(loc) for t in ts]
            cs = [make_coercion(anyt, t, loc) for anyt, t in zip(any_types, ts)]
            return Compose(loc, Project(loc, TupleType(loc, any_types)),
                           CoerceTuple(loc, cs))
        case (_, AnyType()) if source.is_ground():
            return Inject(loc, source)
        case (TupleType(ss), AnyType()):
            any_types = [AnyType(loc) for s in ss]
            cs = [make_coercion(s, anyt, loc) for s, anyt in zip(ss, any_types)]
            return Compose(loc, CoerceTuple(loc, cs),
                           Inject(loc, TupleType(loc, any_types)))
        case (AnyType(), AnyType()):
            return IdCoercion(loc, source)
        case (IntType(), IntType()):
            return IdCoercion(loc, source)
        case (RationalType(), RationalType()):
            return IdCoercion(loc, source)
        case (BoolType(), BoolType()):
            return IdCoercion(loc, source)
        case (VoidType(), VoidType()):
            return IdCoercion(loc, source)
        case (PointerType(s), PointerType(t)):
            rd = make_coercion(s, t, loc)
            wt = make_coercion(t, s, loc)
            # if isinstance(rd, IdCoercion) and isinstance(wt, IdCoercion):
            #     return IdCoercion(loc, source)
            # else:
            #     return CoercePointer(loc, rd, wt)
            return CoercePointer(loc, rd, wt)
        case (ArrayType(s), ArrayType(t)):
            return CoerceArray(loc, make_coercion(s, t, loc), make_coercion(t, s, loc))
        case (TupleType(ss), TupleType(ts)):
            cs = [make_coercion(s, t, loc) for s, t in zip(ss, ts)]
            return CoerceTuple(loc, cs)
        case (RecordType(ss), RecordType(ts)):
            sd = {f: s for (f, s) in ss}
            cs = {f: make_coercion(sd[f], t, loc) for (f, t) in ts}
            return CoerceRecord(loc, cs)
        case (FunctionType(stys, sps, sr, sreqs), FunctionType(ttys, tps, tr, treqs)):
            cps = [make_coercion(tp, sp, loc) for (sp, tp) in zip(sps, tps)]
            cr = make_coercion(sr, tr, loc)
            return CoerceFunction(loc, cps, cr)
        case (VariantType(ss), VariantType(ts)):
            sd = {f: s for (f, s) in ss}
            cs = {f: make_coercion(sd[f], t, loc) for (f, t) in ts}
            return CoerceVariant(loc, cs)
        # todo: type variables, etc.
        # how to handle recursive types? Look at Andre's solution.
        case _:
            raise Exception('make_coercion, unhandled case ' + repr(source) + ' ' + repr(target))


