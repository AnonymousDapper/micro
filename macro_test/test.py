#from micro.macros import quote

from micro import macro


@macro!
def biject(name, reverse_name, **kwargs):
    $name = {}
    for $k, $v in $kwargs:
        $name[quote!($k)] = $v


    $reverse_name = {}
    for $k, $v in $kwargs:
        $reverse_name[$v] = quote!($k)


@macro!
def print_biject(name, reverse_name):
    for k, v in $name.items():
        print(k, v)

    for k, v in $reverse_name.items():
        print(k, v)

biject!(color_to_code, code_to_color, black=0, red=1, green=2, yellow=3, blue=4, magenta=5, cyan=6, white=7)

print_biject!(color_to_code, code_to_color)