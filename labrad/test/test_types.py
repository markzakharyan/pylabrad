# Copyright (C) 2007  Matthew Neeley
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime

import numpy as np
import pytest

import labrad.types as T
import labrad.units as U
from labrad.units import Value, ValueArray, Complex


class TestLabradTypes:

    def test_tags(self):
        """Test the parsing of type tags into Type objects."""
        tests = {
            '_': T.TNone(),
            'b': T.TBool(),
            'i': T.TInt(),
            'w': T.TUInt(),
            's': T.TStr(),
            't': T.TTime(),
            'y': T.TBytes(),

            # clusters
            'ii': T.TCluster(T.TInt(), T.TInt()),
            'b(t)': T.TCluster(T.TBool(), T.TCluster(T.TTime())),
            '(ss)': T.TCluster(T.TStr(), T.TStr()),
            '(s)': T.TCluster(T.TStr()),
            '((siw))': T.TCluster(T.TCluster(T.TStr(), T.TInt(),
                                               T.TUInt())),

            # lists
            '*b': T.TList(T.TBool()),
            '*_': T.TList(),
            '*2b': T.TList(T.TBool(), depth=2),
            '*2_': T.TList(depth=2),
            '*2v[Hz]': T.TList(T.TValue('Hz'), depth=2),
            '*3v': T.TList(T.TValue(), depth=3),
            '*v[]': T.TList(T.TValue(''), depth=1),

            # unit types
            'v': T.TValue(),
            'v[]': T.TValue(''),
            'v[m/s]': T.TValue('m/s'),
            'c': T.TComplex(),
            'c[]': T.TComplex(''),
            'c[m/s]': T.TComplex('m/s'),

            # errors
            'E': T.TError(),
            'Ew': T.TError(T.TUInt()),
            'E(w)': T.TError(T.TCluster(T.TUInt())),

            # more complex stuff
            '*b*i': T.TCluster(T.TList(T.TBool()), T.TList(T.TInt())),
        }
        for tag, type_ in tests.items():
            assert T.parseTypeTag(tag) == type_
            newtag = str(type_)
            if isinstance(type_, T.TCluster) and tag[0] + tag[-1] != '()':
                # just added parentheses in this case
                assert newtag == '(%s)' % tag
            else:
                assert newtag == tag

    def test_tag_comments(self):
        """Test the parsing of type tags with comments and whitespace."""
        tests = {
            '': T.TNone(),
            ' ': T.TNone(),
            ': this is a test': T.TNone(),
            '  : this is a test': T.TNone(),
            '   i  ': T.TInt(),
            '   i  :': T.TInt(),
            '   i  : blah': T.TInt(),
        }
        for tag, type_ in tests.items():
            assert T.parseTypeTag(tag) == type_

    def test_default_flat_and_back(self):
        """
        Test roundtrip python->LabRAD->python conversion.

        No type requirements are given in these tests. In other words, we allow
        pylabrad to choose a default type for flattening.

        In this test, we expect A == unflatten(*flatten(A)). In other words,
        we expect the default type chosen for each object to unflatten as
        an object equal to the one originally flattened.
        """
        tests = [
            # simple types
            None,
            True, False,
            1, -1, 2, -2, 0x7FFFFFFF, -0x80000000,
            '', 'a', '\x00\x01\x02\x03',
            datetime.now(),

            # values
            5.0,
            Value(6, ''),
            Value(7, 'ms'),
            8+0j,
            Complex(9+0j, ''),
            Complex(10+0j, 'GHz'),

            # ValueArray and ndarray
            # These types should be invariant under flattening followed by
            # unflattening. Note, however, that since eg. [1, 2, 3] will
            # unflatten as ndarray with dtype=int32, we do not put lists
            # in this test.
            U.ValueArray([1, 2, 3], 'm'),
            U.ValueArray([1j, 2j, 3j], 's'),
            np.array([1, 3, 4], dtype='int32'),
            np.array([1.1, 2.2, 3.3]),

            # clusters
            (1, True, 'a'),
            ((1, 2), ('a', False)),

            # lists
            [],
            #[1, 2, 3, 4],
            #[1L, 2L, 3L, 4L],
            [[]],
            [['a', 'bb', 'ccc'], ['dddd', 'eeeee', 'ffffff']],

            # more complex stuff
            [(1, 'a'), (2, 'b')],
        ]
        for data_in in tests:
            data_out = T.unflatten(*T.flatten(data_in))
            if isinstance(data_in, U.ValueArray):
                assert data_in.allclose(data_out)
            elif isinstance(data_in, np.ndarray):
                np.testing.assert_array_equal(data_out, data_in)
            else:
                assert data_in == data_out

    def test_default_flat_and_back_non_identical(self):
        """
        Test flattening/unflattening of objects which change type.

        No type requirements are given in these tests. In other words, we allow
        pylabrad to choose a default type for flattening.

        In this test, we do not expect A == unflatten(*flatten(A)). This is
        mostly because list of numbers, both with an without units, should
        unflatten to ndarray or ValueArray, rather than actual python lists.
        """
        def compareValueArrays(a, b):
            """I check near equality of two ValueArrays"""
            assert a.allclose(b)

        tests = [
            ([1, 2, 3], np.array([1, 2, 3], dtype='int32'),
                np.testing.assert_array_equal),
            ([1.1, 2.2, 3.3], np.array([1.1, 2.2, 3.3], dtype='float64'),
                np.testing.assert_array_almost_equal),
            (np.array([3, 4], dtype='int32'), np.array([3, 4], dtype='int32'),
                np.testing.assert_array_equal),
            (np.array([1.2, 3.4]), np.array([1.2, 3.4]),
                np.testing.assert_array_almost_equal),
            ([Value(1.0, 'm'), Value(3.0, 'm')], ValueArray([1.0, 3.0], 'm'),
                compareValueArrays),
            ([Value(1.0, 'm'), Value(10, 'cm')], ValueArray([1.0, 0.1], 'm'),
                compareValueArrays),
            (ValueArray([1, 2], 'Hz'), ValueArray([1, 2], 'Hz'),
                compareValueArrays),
            (ValueArray([1.0, 2], ''), np.array([1.0, 2]),
                np.testing.assert_array_almost_equal),
            # Numpy scalar types
            (np.bool8(True) if hasattr(np, 'bool8') else np.bool_(True), True, None)
        ]
        for input, expected, comparison_func in tests:
            unflat = T.unflatten(*T.flatten(input))
            if isinstance(unflat, np.ndarray):
                assert unflat.dtype == expected.dtype
            if comparison_func:
                comparison_func(unflat, expected)
            else:
                assert unflat == expected

    def test_flat_and_back_with_type_requirements(self):
        tests = [
            ([1, 2, 3], ['*i'], np.array([1, 2, 3]),
                np.testing.assert_array_equal),
            ([1, 2], ['*v[]'], np.array([1, 2]),
                np.testing.assert_array_almost_equal),
            ([1.1, 2.], ['*v[]'], np.array([1.1, 2.], dtype='float64'),
                np.testing.assert_array_almost_equal)
        ]
        for input, types, expected, comparison_func in tests:
            flat = T.flatten(input, types)
            unflat = T.unflatten(*flat)
            comparison_func(expected, unflat)

    def test_boolean_array_flattening(self):
        flat = T.flatten([True, False, True])
        unflat = T.unflatten(*flat)
        flat2 = T.flatten(unflat)
        unflat2 = T.unflatten(*flat2)
        np.testing.assert_array_equal(unflat, unflat2)

    def test_failed_flattening(self):
        """
        Trying to flatten data to an incompatible type should raise an error.
        """
        cases = [
            # Simple cases
            (1, ['s', 'v[Hz]']),
            ('X', ['i', 'v', 'w']),
            (5.0, ['s', 'b', 't', 'w', 'i', 'v[Hz]']),
            # Value
            (5.0, 'v[Hz]'),
            (Value(4, 'm'), 'v[]'),
            (Value(3, 's'), ['v[Hz]', 'i', 'w']),
            # ndarray
            (np.array([1, 2, 3], dtype='int32'), '*v[Hz]'),
            (np.array([1.0, 2.4]), ['*i', '*w']),
            # ValueArray
            (U.ValueArray([1, 2, 3], 'm'), '*v[s]'),
            (U.ValueArray([1, 2], 'm'), '*v[]')
        ]
        for data, targetTag in cases:
            with pytest.raises(T.FlatteningError):
                T.flatten(data, targetTag)

    def testTypeHints(self):
        """Test conversion to specified allowed types."""
        passingTests = [
            # convert to default type
            (1, [], 'i'),

            # convert to first compatible type
            (1, ['s', 'w'], 'w'),
            (1, ['s', 'v'], 'v[]'),
            (1*U.m, ['s', 'v[m]'], 'v[m]'),
            # 'v' not allowed on wire
            (3.0, 'v', 'v[]'),
            (3, 'v', 'v[]'),

            # empty list gets type from hint
            ([], ['s', '*(ww)'], '*(ww)'),

            # handle unknown pieces inside clusters and lists
            (['a', 'b'], ['*?'], '*s'),
            ((1, 2, 'a'), ['ww?'], 'wws'),
            ((1, 2), ['??'], 'iw'),
        ]
        for data, hints, tag in passingTests:
            assert T.flatten(data, hints)[1] == T.parseTypeTag(tag)

    def test_type_specialization(self):
        """Test specialization of the type during flattening."""
        tests = [
            # specialization without hints
            ([([],), ([5.0],)], '*(*v)'),
            ([([],), ([Value(5, 'm')],)], '*(*v[m])'),
        ]
        for data, tag in tests:
            assert T.flatten(data)[1] == T.parseTypeTag(tag)

    def test_unit_types(self):
        """Test flattening with units.

        The flattening code should not do unit conversion,
        but should leave that up to the LabRAD manager to handle.
        Basically, for purposes of flattening, a unit is a unit.
        """
        tests = [
            (Value(5.0, 'ft'), ['v[m]'], 'v[ft]'),

            # real value array
            (U.ValueArray([1, 2, 3], ''), [], '*v[]'),
            (U.ValueArray([1, 2, 3], 'm'), ['*v[m]'], '*v[m]'),

            # complex value array
            (U.ValueArray([1j, 2j, 3j], ''), [], '*c[]'),
            (U.ValueArray([1j, 2j, 3j], 'm'), [], '*c[m]')
        ]
        for data, hints, tag in tests:
            assert T.flatten(data, hints)[1] == T.parseTypeTag(tag)

        # we disallow flattening a float to a value with units,
        # as this is a major source of bugs
        with pytest.raises(Exception):
            T.flatten(5.0, 'v[m]')

    def test_numpy_support(self):
        """Test flattening and unflattening of numpy arrays"""
        # TODO: flesh this out with more array types
        a = np.array([1, 2, 3, 4, 5], dtype='int32')
        b = T.unflatten(*T.flatten(a))
        assert np.all(a == b)
        assert T.flatten(np.int32(5))[0] == b'\x00\x00\x00\x05'
        assert T.flatten(np.int64(-5))[0] == b'\xff\xff\xff\xfb'
        assert len(T.flatten(np.float64(3.15))[0]) == 8
        with pytest.raises(T.FlatteningError):
            T.flatten(np.int64(-5), T.TUInt())

    def test_numpy_array_scalar(self):
        with pytest.raises(TypeError):
            T.flatten(np.array(5))
        with pytest.raises(TypeError):
            T.flatten(U.ValueArray(np.array(5), 'ns'))


    def test_integer_ranges(self):
        """Test flattening of out-of-range integer values"""
        tests = [
            (0x80000000, 'i'),
            (-0x80000001, 'i'),
            (0x100000000, 'w'),
            (-1, 'w')
        ]
        for n, t in tests:
            with pytest.raises(T.FlatteningError):
                T.flatten(n, t)

    def test_flatten_is_idempotent(self):
        flat = T.flatten(0x1, 'i')
        assert T.flatten(flat) == flat
        assert T.flatten(flat, 'i') == flat
        with pytest.raises(T.FlatteningError):
            T.flatten(flat, 'v')

    def test_eval_datetime(self):
        data = datetime.now()
        data2 = T.evalLRData(repr(data))
        assert data == data2

    def test_unicode_bytes(self):
        foo = T.flatten('foo bar')
        assert foo == T.flatten(u'foo bar')
        assert str(foo.tag) == 's'
        assert T.unflatten(foo.bytes, 'y') == b'foo bar'
        assert T.unflatten(*T.flatten(b'foo bar', ['y'])) == b'foo bar'

    def test_flatten_int_array_to_value_array(self):
        x = np.array([1, 2, 3, 4], dtype='int64')
        flat = T.flatten(x, '*v')
        y = T.unflatten(*flat)
        assert np.all(x == y)

    def test_flatten_array_to_cluster_list(self):
        """Fail if trying to flatten a numpy array to type with incorrect shape.

        See https://github.com/labrad/pylabrad/issues/290.
        """
        arr = np.arange(5, dtype='float64')
        with pytest.raises(T.FlatteningError):
            T.flatten(arr, types=['*(v, v)'])

    def test_can_flatten_flat_data(self):
        x = ('this is a test', -42, [False, True])
        flat = T.flatten(x)
        assert T.parseTypeTag(flat.tag) == T.parseTypeTag('si*b')
        flat2 = T.flatten(x)
        assert flat2 == flat
        flat3 = T.flatten(x, 'si*b')
        assert flat3 == flat
        with pytest.raises(T.FlatteningError):
            T.flatten(x, 'sv')

    def test_can_flatten_list_of_partial_flat_data(self):
        x1 = ('this is a test', -42, [False, True])
        piece1 = T.flatten(x1)
        x2 = ('this is also a test', -43, [False, True, True, True])
        piece2 = T.flatten(x2)

        not_flattened = [x1, x2]
        partially_flattened = [piece1, piece2]
        tag = '*(si*b)'

        expected = T.flatten(not_flattened)

        flat1 = T.flatten(partially_flattened)
        assert flat1 == expected

        flat2 = T.flatten(partially_flattened, tag)
        assert flat2 == expected

        with pytest.raises(T.FlatteningError):
            T.flatten(partially_flattened, '*(si)')

    def test_can_flatten_cluster_of_partial_flat_data(self):
        x1 = ('this is a test', -42, [False, True])
        piece1 = T.flatten(x1)
        x2 = ('this is also a test', -43, [False, True, True, True])
        piece2 = T.flatten(x2)

        not_flattened = (('1', x1), ('2', x2, False))
        partially_flattened = (('1', piece1), ('2', piece2, False))
        tag = '((s(si*b)) (s(si*b)b))'

        expected = T.flatten(not_flattened)

        flat1 = T.flatten(partially_flattened)
        assert flat1 == expected

        flat2 = T.flatten(partially_flattened, tag)
        assert flat2 == expected

        with pytest.raises(T.FlatteningError):
            T.flatten(partially_flattened, '*(s(si*b))')
