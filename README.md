# micro

Tiny AST macro lib.


# Examples

```py
    # Repetition

    @macro!
    def foo(*args):
        for $a in $args:
            do_something($a)

    foo!(1, 2, 3, 4)
    # > do_something(1)
    # > do_something(2)
    # > do_something(3)
    # > do_something(4)

    @macro!
    def foo(**kwargs):
        for! $k, $v in $kwargs:
            do_something($k, $v)

    foo!(a=1, b=2, c=3, d=4)
    # > do_something(a, 1)
    # > do_something(b, 2)
    # > do_something(c, 3)
    # > do_something(d, 4)


    # Quoting

    print(quote!(5 + 3 / 2), "=", 5 + 3 / 2)
    # > 5 + 3 / 2 = 6.5
```