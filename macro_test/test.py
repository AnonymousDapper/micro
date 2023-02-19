#from micro.macros import quote

from micro import macro


# @macro!
# def lprint(*text):
#     with $text as $c:
#         print($c)

# @macro!
# def foo(**k):
#     for $a, $b in $k:
#         print(quote!($a.$b), "=>", $b)

# foo!(a=1, b=2, c=3, d=4)

# @macro!
# def fullwidth(text):
#     " ".join(list($text))

# print(fullwidth!("hello, world"))

# print(" ".join(list("dlrow ,olleh")))

# lprint!("g", "o", "t", "y", "a")


print(quote!(5 + 3 / 2), " = ", 5 + 3 / 2)