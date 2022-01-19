# metaclass定义
class Registar(type):
    def __init__(cls, name, bases, dct):
        if not hasattr(cls, '_registry'):
            cls._registry = {}
        else:
            cls._registry[name.lower()] = cls
        super(Registar, cls).__init__(name, bases, dct)
    def build(cls, key, *args, **kwargs):
        # 实例化对象
        return cls._registry[key.lower()](*args, **kwargs)

# 基类
class A(object, metaclass=Registar):
    alice="a"

class B(A):
    pass
class C(A):
    pass

# 父类是metaclass的一个实例，故可以打印其_registry属性。
# 子类能继承父类的类属性
print(A._registry)
print(B._registry)

# 调用metaclass函数来实例化对应类的对象
o2 = A.build("B")
o3 = A.build("c")
print(o2)
print(o3)