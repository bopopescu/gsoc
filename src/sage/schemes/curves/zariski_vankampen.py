r"""
Zariski-Van Kampen method implementation

This file contains functions to compute the fundamental group of
the complement of a curve in the complex affine or projective plane,
using Zariski-Van Kampen approach. It depends on the package ``sirocco``.

The current implementation allows to compute a presentation of the
fundamental group of curves over the rationals or number fields with
a fixed embedding on `\QQbar`.

Instead of computing a representation of the braid monodromy, we
choose several base points and a system of paths joining them that
generate all the necessary loops around the points of the discriminant.
The group is generated by the free groups over these points, and
braids over this paths gives relations between these generators.
This big group presentation is simplified at the end.

.. TODO::

    Implement the complete braid monodromy approach.

AUTHORS:

- Miguel Marco (2015-09-30): Initial version

EXAMPLES::

    sage: from sage.schemes.curves.zariski_vankampen import fundamental_group # optional - sirocco
    sage: R.<x,y> = QQ[]
    sage: f = y^3 + x^3 -1
    sage: fundamental_group(f) # optional - sirocco
    Finitely presented group < x0 |  >
"""
# ****************************************************************************
#       Copyright (C) 2015 Miguel Marco <mmarco@unizar.es>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#                  https://www.gnu.org/licenses/
# ****************************************************************************
from __future__ import division, absolute_import

from sage.groups.braid import BraidGroup
from sage.groups.perm_gps.permgroup_named import SymmetricGroup
from sage.rings.rational_field import QQ
from sage.rings.qqbar import QQbar
from sage.rings.all import CC
from sage.parallel.decorate import parallel
from sage.misc.flatten import flatten
from sage.groups.free_group import FreeGroup
from sage.misc.misc_c import prod
from sage.rings.complex_field import ComplexField
from sage.rings.complex_interval_field import ComplexIntervalField
from sage.combinat.permutation import Permutation
from sage.functions.generalized import sign


def braid_from_piecewise(strands):
    r"""
    Compute the braid corresponding to the piecewise linear curves strands.

    INPUT:

    - ``strands`` -- a list of lists of tuples ``(t, c)``, where ``t``
      is a number bewteen 0 and 1, and ``c`` is a complex number

    OUTPUT:

    The braid formed by the piecewise linear strands.

    EXAMPLES::

        sage: from sage.schemes.curves.zariski_vankampen import braid_from_piecewise # optional - sirocco
        sage: paths = [[(0, I), (0.2, -1 - 0.5*I), (0.8, -1), (1, -I)],
        ....:          [(0, -1), (0.5, -I), (1, 1)],
        ....:          [(0, 1), (0.5, 1 + I), (1, I)]]
        sage: braid_from_piecewise(paths) # optional - sirocco
        s0*s1
    """
    L = strands
    i = min(val[1][0] for val in L)
    totalpoints = [[[a[0][1].real(), a[0][1].imag()]] for a in L]
    indices = [1 for a in range(len(L))]
    while i < 1:
        for j, val in enumerate(L):
            if val[indices[j]][0] > i:
                xaux = val[indices[j] - 1][1]
                yaux = val[indices[j]][1]
                aaux = val[indices[j] - 1][0]
                baux = val[indices[j]][0]
                interpola = xaux + (yaux - xaux) * (i - aaux) / (baux - aaux)
                totalpoints[j].append([interpola.real(), interpola.imag()])
            else:
                totalpoints[j].append([val[indices[j]][1].real(),
                                       val[indices[j]][1].imag()])
                indices[j] = indices[j] + 1
        i = min(val[indices[k]][0] for k, val in enumerate(L))

    for j, val in enumerate(L):
        totalpoints[j].append([val[-1][1].real(), val[-1][1].imag()])

    braid = []
    G = SymmetricGroup(len(totalpoints))

    def sgn(x, y):
        if x < y:
            return 1
        if x > y:
            return -1
        return 0
    for i in range(len(totalpoints[0]) - 1):
        l1 = [totalpoints[j][i] for j in range(len(L))]
        l2 = [totalpoints[j][i + 1] for j in range(len(L))]
        M = [[l1[s], l2[s]] for s in range(len(l1))]
        M.sort()
        l1 = [a[0] for a in M]
        l2 = [a[1] for a in M]
        cruces = []
        for j in range(len(l2)):
            for k in range(j):
                if l2[j] < l2[k]:
                    t = (l1[j][0] - l1[k][0])/(l2[k][0] - l1[k][0] + l1[j][0] - l2[j][0])
                    s = sgn(l1[k][1]*(1 - t) + t*l2[k][1], l1[j][1]*(1 - t) + t*l2[j][1])
                    cruces.append([t, k, j, s])
        if cruces:
            cruces.sort()
            P = G(Permutation([]))
            while cruces:
                # we select the crosses in the same t
                crucesl = [c for c in cruces if c[0] == cruces[0][0]]
                crossesl = [(P(c[2] + 1) - P(c[1] + 1), c[1], c[2], c[3])
                            for c in crucesl]
                cruces = cruces[len(crucesl):]
                while crossesl:
                    crossesl.sort()
                    c = crossesl.pop(0)
                    braid.append(c[3]*min(map(P, [c[1] + 1, c[2] + 1])))
                    P = G(Permutation([(c[1] + 1, c[2] + 1)])) * P
                    crossesl = [(P(cr[2]+1) - P(cr[1]+1), cr[1], cr[2], cr[3])
                                for cr in crossesl]

    B = BraidGroup(len(L))
    return B(braid)


def discrim(f):
    r"""
    Return the points in the discriminant of ``f``.

    The result is the set of values of the first variable for which
    two roots in the second variable coincide.

    INPUT:

    - ``f`` -- a polynomial in two variables with coefficients in a
      number field with a fixed embedding in `\QQbar`

    OUTPUT:

    A list with the values of the discriminant in `\QQbar`.

    EXAMPLES::

        sage: from sage.schemes.curves.zariski_vankampen import discrim # optional - sirocco
        sage: R.<x,y> = QQ[]
        sage: f = (y^3 + x^3 - 1) * (x + y)
        sage: discrim(f) # optional - sirocco
        [1,
        -0.500000000000000? - 0.866025403784439?*I,
        -0.500000000000000? + 0.866025403784439?*I]
    """
    x, y = f.variables()
    F = f.base_ring()
    poly = F[x](f.discriminant(y).resultant(f, y)).radical()
    return poly.roots(QQbar, multiplicities=False)


def segments(points):
    """
    Return the bounded segments of the Voronoi diagram of the given points.

    INPUT:

    - ``points`` -- a list of complex points

    OUTPUT:

    A list of pairs ``(p1, p2)``, where ``p1`` and ``p2`` are the
    endpoints of the segments in the Voronoi diagram.

    EXAMPLES::

        sage: from sage.schemes.curves.zariski_vankampen import discrim, segments # optional - sirocco
        sage: R.<x,y> = QQ[]
        sage: f = y^3 + x^3 - 1
        sage: disc = discrim(f) # optional - sirocco
        sage: segments(disc) # optional - sirocco # abs tol 1e-15
        [(-2.84740787203333 - 2.84740787203333*I,
        -2.14285714285714 + 1.11022302462516e-16*I),
        (-2.84740787203333 + 2.84740787203333*I,
        -2.14285714285714 + 1.11022302462516e-16*I),
        (2.50000000000000 + 2.50000000000000*I,
        1.26513881334184 + 2.19128470333546*I),
        (2.50000000000000 + 2.50000000000000*I,
        2.50000000000000 - 2.50000000000000*I),
        (1.26513881334184 + 2.19128470333546*I, 0.000000000000000),
        (0.000000000000000, 1.26513881334184 - 2.19128470333546*I),
        (2.50000000000000 - 2.50000000000000*I,
        1.26513881334184 - 2.19128470333546*I),
        (-2.84740787203333 + 2.84740787203333*I,
        1.26513881334184 + 2.19128470333546*I),
        (-2.14285714285714 + 1.11022302462516e-16*I, 0.000000000000000),
        (-2.84740787203333 - 2.84740787203333*I,
        1.26513881334184 - 2.19128470333546*I)]
    """
    from numpy import array, vstack
    from scipy.spatial import Voronoi
    discpoints = array([(CC(a).real(), CC(a).imag()) for a in points])
    added_points = 3 * abs(discpoints).max() + 1.0
    configuration = vstack([discpoints, array([[added_points, 0],
                                               [-added_points, 0],
                                               [0, added_points],
                                               [0, -added_points]])])
    V = Voronoi(configuration)
    res = []
    for rv in V.ridge_vertices:
        if -1 not in rv:
            p1 = CC(list(V.vertices[rv[0]]))
            p2 = CC(list(V.vertices[rv[1]]))
            res.append((p1, p2))
    return res


def followstrand(f, x0, x1, y0a, prec=53):
    r"""
    Return a piecewise linear approximation of the homotopy continuation
    of the root ``y0a`` from ``x0`` to ``x1``.

    INPUT:

    - ``f`` -- a polynomial in two variables
    - ``x0`` -- a complex value, where the homotopy starts
    - ``x1`` -- a complex value, where the homotopy ends
    - ``y0a`` -- an approximate solution of the polynomial `F(y) = f(x_0, y)`
    - ``prec`` -- the precision to use

    OUTPUT:

    A list of values `(t, y_{tr}, y_{ti})` such that:

    - ``t`` is a real number between zero and one
    - `f(t \cdot x_1 + (1-t) \cdot x_0, y_{tr} + I \cdot y_{ti})`
      is zero (or a good enough approximation)
    - the piecewise linear path determined by the points has a tubular
      neighborhood  where the actual homotopy continuation path lies, and
      no other root intersects it.

    EXAMPLES::

        sage: from sage.schemes.curves.zariski_vankampen import followstrand # optional - sirocco
        sage: R.<x,y> = QQ[]
        sage: f = x^2 + y^3
        sage: x0 = CC(1, 0)
        sage: x1 = CC(1, 0.5)
        sage: followstrand(f, x0, x1, -1.0) # optional - sirocco # abs tol 1e-15
        [(0.0, -1.0, 0.0),
         (0.7500000000000001, -1.015090921153253, -0.24752813818386948),
         (1.0, -1.026166099551513, -0.32768940253604323)]
    """
    CIF = ComplexIntervalField(prec)
    CC = ComplexField(prec)
    G = f.change_ring(QQbar).change_ring(CIF)
    (x, y) = G.variables()
    g = G.subs({x: (1 - x) * CIF(x0) + x * CIF(x1)})
    coefs = []
    deg = g.total_degree()
    for d in range(deg + 1):
        for i in range(d + 1):
            c = CIF(g.coefficient({x: d - i, y: i}))
            cr = c.real()
            ci = c.imag()
            coefs += list(cr.endpoints())
            coefs += list(ci.endpoints())
    yr = CC(y0a).real()
    yi = CC(y0a).imag()
    from sage.libs.sirocco import contpath, contpath_mp
    try:
        if prec == 53:
            points = contpath(deg, coefs, yr, yi)
        else:
            points = contpath_mp(deg, coefs, yr, yi, prec)
        return points
    except Exception:
        return followstrand(f, x0, x1, y0a, 2 * prec)


@parallel
def braid_in_segment(f, x0, x1):
    """
    Return the braid formed by the `y` roots of ``f`` when `x` moves
    from ``x0`` to ``x1``.

    INPUT:

    - ``f`` -- a polynomial in two variables
    - ``x0`` -- a complex number
    - ``x1`` -- a complex number

    OUTPUT:

    A braid.

    EXAMPLES::

        sage: from sage.schemes.curves.zariski_vankampen import braid_in_segment # optional - sirocco
        sage: R.<x,y> = QQ[]
        sage: f = x^2 + y^3
        sage: x0 = CC(1,0)
        sage: x1 = CC(1, 0.5)
        sage: braid_in_segment(f, x0, x1) # optional - sirocco
        s1

    TESTS:

    Check that :trac:`26503` is fixed::

        sage: wp = QQ['t']([1, 1, 1]).roots(QQbar)[0][0]
        sage: Kw.<wp> = NumberField(wp.minpoly(), embedding=wp)
        sage: R.<x, y> = Kw[]
        sage: z = -wp - 1
        sage: f = y*(y + z)*x*(x - 1)*(x - y)*(x + z*y - 1)*(x + z*y + wp)
        sage: from sage.schemes.curves import zariski_vankampen as zvk
        sage: g = f.subs({x: x + 2*y})
        sage: p1 = QQbar(sqrt(-1/3))
        sage: p2 = QQbar(1/2+sqrt(-1/3)/2)
        sage: B = zvk.braid_in_segment(g,CC(p1),CC(p2)) # optional - sirocco
        sage: B.left_normal_form()  # optional - sirocco
        (1, s5)
    """
    CC = ComplexField(64)
    (x, y) = f.variables()
    I = QQbar.gen()
    X0 = QQ(x0.real()) + I * QQ(x0.imag())
    X1 = QQ(x1.real()) + I * QQ(x1.imag())
    F0 = QQbar[y](f(X0, y))
    y0s = F0.roots(multiplicities=False)
    strands = [followstrand(f, x0, x1, CC(a)) for a in y0s]
    complexstrands = [[(a[0], CC(a[1], a[2])) for a in b] for b in strands]
    centralbraid = braid_from_piecewise(complexstrands)
    initialstrands = []
    y0aps = [c[0][1] for c in complexstrands]
    used = []
    for y0ap in y0aps:
        distances = [((y0ap - y0).norm(), y0) for y0 in y0s]
        y0 = sorted(distances)[0][1]
        if y0 in used:
            raise ValueError("different roots are too close")
        used.append(y0)
        initialstrands.append([(0, y0), (1, y0ap)])
    initialbraid = braid_from_piecewise(initialstrands)
    F1 = QQbar[y](f(X1, y))
    y1s = F1.roots(multiplicities=False)
    finalstrands = []
    y1aps = [c[-1][1] for c in complexstrands]
    used = []
    for y1ap in y1aps:
        distances = [((y1ap - y1).norm(), y1) for y1 in y1s]
        y1 = sorted(distances)[0][1]
        if y1 in used:
            raise ValueError("different roots are too close")
        used.append(y1)
        finalstrands.append([(0, y1ap), (1, y1)])
    finallbraid = braid_from_piecewise(finalstrands)
    return initialbraid * centralbraid * finallbraid


def fundamental_group(f, simplified=True, projective=False):
    r"""
    Return a presentation of the fundamental group of the complement of
    the algebraic set defined by the polynomial ``f``.

    INPUT:

    - ``f`` -- a polynomial in two variables, with coefficients in either
      the rationals or a number field with a fixed embedding in `\QQbar`

    - ``simplified`` -- boolean (default: ``True``); if set to ``True`` the
      presentation will be simplified (see below)

    - ``projective`` -- boolean (default: ``False``); if set to ``True``,
      the fundamental group of the complement of the projective completion
      of the curve will be computed, otherwise, the fundamental group of
      the complement in the affine plane will be computed

    If ``simplified`` is ``False``, the returned presentation has as
    many generators as degree of the polynomial times the points in the
    base used to create the segments that surround the discriminant. In
    this case, the generators are granted to be meridians of the curve.

    OUTPUT:

    A presentation of the fundamental group of the complement of the
    curve defined by ``f``.

    EXAMPLES::

        sage: from sage.schemes.curves.zariski_vankampen import fundamental_group # optional - sirocco
        sage: R.<x,y> = QQ[]
        sage: f = x^2 + y^3
        sage: fundamental_group(f) # optional - sirocco
        Finitely presented group < ... >
        sage: fundamental_group(f, simplified=False) # optional - sirocco
        Finitely presented group < ... >

    ::

        sage: from sage.schemes.curves.zariski_vankampen import fundamental_group # optional - sirocco
        sage: R.<x,y> = QQ[]
        sage: f = y^3 + x^3
        sage: fundamental_group(f) # optional - sirocco
        Finitely presented group < ... >

    It is also possible to have coefficients in a number field with a
    fixed embedding in `\QQbar`::

        sage: from sage.schemes.curves.zariski_vankampen import fundamental_group # optional - sirocco
        sage: zeta = QQbar['x']('x^2+x+1').roots(multiplicities=False)[0]
        sage: zeta
        -0.50000000000000000? - 0.866025403784439?*I
        sage: F = NumberField(zeta.minpoly(), 'zeta', embedding=zeta)
        sage: F.inject_variables()
        Defining zeta
        sage: R.<x,y> = F[]
        sage: f = y^3 + x^3 +zeta *x + 1
        sage: fundamental_group(f) # optional - sirocco
        Finitely presented group < x0 |  >
    """
    (x, y) = f.variables()
    F = f.base_ring()
    g = f.radical()
    d = g.degree(y)
    while not g.coefficient(y**d) in F or (projective and g.total_degree() > d):
        g = g.subs({x: x + y})
        d = g.degree(y)
    disc = discrim(g)
    segs = segments(disc)
    vertices = list(set(flatten(segs)))
    Faux = FreeGroup(d)
    F = FreeGroup(d * len(vertices))
    rels = []
    if projective:
        rels.append(prod(F.gen(i) for i in range(d)))
    braidscomputed = braid_in_segment([(g, seg[0], seg[1]) for seg in segs])
    for braidcomputed in braidscomputed:
        seg = (braidcomputed[0][0][1], braidcomputed[0][0][2])
        b = braidcomputed[1]
        i = vertices.index(seg[0])
        j = vertices.index(seg[1])
        for k in range(d):
            el1 = Faux([k + 1]) * b.inverse()
            el2 = k + 1
            w1 = F([sign(a) * d * i + a for a in el1.Tietze()])
            w2 = F([d * j + el2])
            rels.append(w1 / w2)
    G = F / rels
    if simplified:
        return G.simplified()
    else:
        return G
