# Copyright (c) 2018, NVIDIA CORPORATION.

import pytest
from collections import OrderedDict

import numpy as np
import pandas as pd

from io import StringIO
from io import BytesIO

from cudf import read_csv
from cudf.io.csv import read_csv_strings
import cudf
import nvstrings
from cudf.tests.utils import assert_eq
import gzip
import shutil
import os

from libgdf_cffi import GDFError


def make_numeric_dataframe(nrows, dtype):
    df = pd.DataFrame()
    df['col1'] = np.arange(nrows, dtype=dtype)
    df['col2'] = np.arange(1, 1 + nrows, dtype=dtype)
    return df


def make_datetime_dataframe():
    df = pd.DataFrame()
    df['col1'] = np.array(['31/10/2010', '05/03/2001', '20/10/1994',
                          '18/10/1990', '1/1/1970', '2016-04-30T01:02:03.400'])
    df['col2'] = np.array(['18/04/1995', '14 / 07 / 1994', '07/06/2006',
                          '16/09/2005', '2/2/1970', '2007-4-30 1:6:40.000PM'])
    return df


def make_numpy_mixed_dataframe():
    df = pd.DataFrame()
    df['Integer'] = np.array([2345, 11987, 9027, 9027])
    df['Date'] = np.array(['18/04/1995', '14/07/1994', '07/06/2006',
                          '16/09/2005'])
    df['Float'] = np.array([9.001, 8.343, 6, 2.781])
    df['Integer2'] = np.array([2345, 106, 2088, 789277])
    df['Category'] = np.array(['M', 'F', 'F', 'F'])
    return df


def make_all_numeric_dtypes_dataframe():
    df = pd.DataFrame()

    gdf_dtypes = ["float", "float32", "float64", "double", "short", "int",
                  "int32", "int64", "long"]

    np_dtypes = [np.float32, np.float32, np.float64, np.float64, np.int16,
                 np.int32, np.int32, np.int64, np.int64]

    for i in range(len(gdf_dtypes)):
        df[gdf_dtypes[i]] = np.arange(10, dtype=np_dtypes[i])

    return (
        df,
        OrderedDict(zip(gdf_dtypes, gdf_dtypes)),
        OrderedDict(zip(gdf_dtypes, np_dtypes))
    )


dtypes = [np.float64, np.float32, np.int64, np.int32]
dtypes_dict = {'1': np.float64, '2': np.float32, '3': np.int64, '4': np.int32}
nelem = [5, 25, 100]


@pytest.mark.parametrize('dtype', dtypes)
@pytest.mark.parametrize('nelem', nelem)
def test_csv_reader_numeric_data(dtype, nelem, tmpdir):

    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file1.csv")

    df = make_numeric_dataframe(nelem, dtype)
    df.to_csv(fname, index=False, header=False)

    dtypes = [df[k].dtype for k in df.columns]
    out = read_csv(str(fname), names=list(df.columns.values), dtype=dtypes)

    assert len(out.columns) == len(df.columns)
    pd.util.testing.assert_frame_equal(df, out.to_pandas())


def test_csv_reader_datetime_data(tmpdir):

    fname = tmpdir.mkdir("gdf_csv").join('tmp_csvreader_file2.csv')

    df = make_datetime_dataframe()
    df.to_csv(fname, index=False, header=False)

    df_out = pd.read_csv(fname, names=['col1', 'col2'], parse_dates=[0, 1],
                         dayfirst=True)
    dtypes = ['date', 'date']
    out = read_csv(str(fname), names=list(df.columns.values), dtype=dtypes,
                   dayfirst=True)

    assert len(out.columns) == len(df_out.columns)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())


@pytest.mark.parametrize('pandas_arg', [
        {'delimiter': '|'},
        {'sep': '|'}
    ])
@pytest.mark.parametrize('cudf_arg', [
        {'sep': '|'},
        {'delimiter': '|'}
    ])
def test_csv_reader_mixed_data_delimiter_sep(tmpdir, pandas_arg, cudf_arg):

    fname = tmpdir.mkdir("gdf_csv").join('tmp_csvreader_file3.csv')

    df = make_numpy_mixed_dataframe()
    df.to_csv(fname, sep='|', index=False, header=False)

    gdf1 = read_csv(str(fname), names=['1', '2', '3', '4', '5'],
                    dtype=['int64', 'date', 'float64', 'int64', 'category'],
                    dayfirst=True, **cudf_arg)
    gdf2 = read_csv(str(fname), names=['1', '2', '3', '4', '5'],
                    dtype=['int64', 'date', 'float64', 'int64', 'category'],
                    dayfirst=True, **pandas_arg)

    pdf = pd.read_csv(fname, names=['1', '2', '3', '4', '5'],
                      parse_dates=[1], dayfirst=True, **pandas_arg)

    assert len(gdf1.columns) == len(pdf.columns)
    assert len(gdf2.columns) == len(pdf.columns)
    assert_eq(gdf1, gdf2)


def test_csv_reader_all_numeric_dtypes(tmpdir):

    # fname = os.path.abspath('cudf/tests/data/tmp_csvreader_file4.csv')
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file4.csv")

    df, gdf_dict, pd_dict = make_all_numeric_dtypes_dataframe()
    df.to_csv(fname, sep=',', index=False, header=False)

    out = read_csv(str(fname), delimiter=',', names=list(gdf_dict.keys()),
                   dtype=gdf_dict)
    df_out = pd.read_csv(fname, delimiter=',', names=list(pd_dict.keys()),
                         dtype=pd_dict, dayfirst=True)

    assert len(out.columns) == len(df_out.columns)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())


def test_csv_reader_skiprows_skipfooter(tmpdir):

    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file5.csv")

    df = make_numpy_mixed_dataframe()
    df.to_csv(fname, columns=['Integer', 'Date', 'Float'], index=False,
              header=False)

    # Using engine='python' to eliminate pandas warning of using python engine.
    df_out = pd.read_csv(fname, names=['1', '2', '3'], parse_dates=[1],
                         dayfirst=True, skiprows=1, skipfooter=1,
                         engine='python')
    out = read_csv(str(fname), names=['1', '2', '3'],
                   dtype=['int64', 'date', 'float64'], skiprows=1,
                   skipfooter=1, dayfirst=True)

    assert len(out.columns) == len(df_out.columns)
    assert len(out) == len(df_out)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())


def test_csv_reader_negative_vals(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file6.csv")

    names = ['0', '1', '2']
    dtypes = ['float32', 'float32', 'float32']
    lines = [','.join(names),
             '-181.5060,-185.37000,-3',
             '-127.6300,-230.54600,-9']

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    zero = [-181.5060, -127.6300]
    one = [-185.370, -230.54600]
    two = [-3, -9]

    df = read_csv(str(fname), names=names, dtype=dtypes, skiprows=1)

    np.testing.assert_allclose(zero, df['0'])
    np.testing.assert_allclose(one, df['1'])
    np.testing.assert_allclose(two, df['2'])


def test_csv_reader_strings(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file7.csv")

    names = ['text', 'int']
    dtypes = ['str', 'int']
    lines = [','.join(names), 'a,0', 'b,0', 'c,0', 'd,0']

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    cols = read_csv_strings(str(fname), names=names, dtype=dtypes, skiprows=1,
                            decimal='.', thousands="'")

    assert(len(cols) == 2)
    assert(type(cols[0]) == nvstrings.nvstrings)
    assert(type(cols[1]) == cudf.Series)
    assert(cols[0].sublist([0]).to_host()[0] == 'a')
    assert(cols[0].sublist([1]).to_host()[0] == 'b')
    assert(cols[0].sublist([2]).to_host()[0] == 'c')
    assert(cols[0].sublist([3]).to_host()[0] == 'd')


def test_csv_reader_strings_quotechars(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file8.csv")

    names = ['text', 'int']
    dtypes = ['str', 'int']
    lines = [','.join(names), '"a,\n",0', '"b ""c"" d",0', 'e,0', '"f,,!.,",0']

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    cols = read_csv_strings(str(fname), names=names, dtype=dtypes, skiprows=1,
                            quotechar='\"', quoting=True)

    assert(len(cols) == 2)
    assert(type(cols[0]) == nvstrings.nvstrings)
    assert(type(cols[1]) == cudf.Series)
    assert(cols[0].sublist([0]).to_host()[0] == 'a,\n')
    assert(cols[0].sublist([1]).to_host()[0] == 'b "c" d')
    assert(cols[0].sublist([2]).to_host()[0] == 'e')
    assert(cols[0].sublist([3]).to_host()[0] == 'f,,!.,')


def test_csv_reader_auto_column_detection(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file9.csv")
    df = make_numpy_mixed_dataframe()
    df.to_csv(fname, columns=['Integer', 'Date', 'Float'], index=False,
              header=False)

    df_out = pd.read_csv(fname, parse_dates=[1], dayfirst=True)
    out = read_csv(str(fname), dayfirst=True)
    assert len(out.columns) == len(df_out.columns)
    assert len(out) == len(df_out)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())
    # Check dtypes
    assert list(df_out.dtypes) == list(out.to_pandas().dtypes)


def test_csv_reader_usecols_int_char(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file10.csv")
    df = make_numpy_mixed_dataframe()
    df.to_csv(fname, columns=['Integer', 'Date', 'Float', 'Integer2'],
              index=False, header=False)

    df_out = pd.read_csv(fname, usecols=[0, 1, 3], parse_dates=[1],
                         dayfirst=True)
    out = read_csv(str(fname), usecols=[0, 1, 3], dayfirst=True)

    assert len(out.columns) == len(df_out.columns)
    assert len(out) == len(df_out)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas(),
                                       check_names=False)


def test_csv_reader_mangle_dupe_cols_header(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file11.csv")
    df = make_numpy_mixed_dataframe()
    df.to_csv(fname, columns=['Integer', 'Date', 'Float', 'Integer2'],
              index=False, header=False)

    # Default: header=0 when names not passed, mangle_dupe_cols = True
    df_out = pd.read_csv(fname, parse_dates=[1], dayfirst=True)
    out = read_csv(str(fname), dayfirst=True)
    assert len(out.columns) == len(df_out.columns)
    assert len(out) == len(df_out)
    # Compare mangled column names for duplicate names in header row
    assert list(df_out.columns.values) == list(out.columns.values)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())

    # header = 3
    df_out = pd.read_csv(fname, parse_dates=[1], dayfirst=True, header=2)
    out = read_csv(str(fname), dayfirst=True, header=2)
    assert len(out.columns) == len(df_out.columns)
    # assert len(out) == len(df_out)
    # Compare column names
    assert list(df_out.columns.values) == list(out.columns.values)


def test_csv_reader_float_decimal(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file12.csv")

    names = ['basic_32', 'basic_64', 'round', 'decimal_only']
    dtypes = ['float32', 'float64', 'float64', 'float32']
    lines = [';'.join(names),
             '1,2;1234,5678;12345;0,123',
             '3,4;3456,7890;67890;,456',
             '5,6e0;0,5679e2;1,2e10;0,07e-1']

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    basic_32_ref = [1.2, 3.4, 5.6]
    basic_64_ref = [1234.5678, 3456.7890, 56.79]
    round_ref = [12345, 67890, 12000000000]
    decimal_only_ref = [0.123, 0.456, 0.007]

    df = read_csv(str(fname), names=names, dtype=dtypes, skiprows=1,
                  delimiter=';', decimal=',')

    np.testing.assert_allclose(basic_32_ref, df['basic_32'])
    np.testing.assert_allclose(basic_64_ref, df['basic_64'])
    np.testing.assert_allclose(round_ref, df['round'])
    np.testing.assert_allclose(decimal_only_ref, df['decimal_only'])


def test_csv_reader_NaN_values():

    names = dtypes = ['float32']
    empty_cells = '\n""\n"  "\n " " \n'
    default_na_cells = ('#N/A\n#N/A N/A\n#NA\n-1.#IND\n'
                        '-1.#QNAN\n-NaN\n-nan\n1.#IND\n'
                        '1.#QNAN\nN/A\nNA\nNULL\n'
                        'NaN\nn/a\nnan\nnull\n')
    custom_na_cells = 'NV_NAN\nNotANumber\n'
    all_cells = empty_cells + default_na_cells + custom_na_cells
    custom_na_values = ['NV_NAN', 'NotANumber']

    # test default NA values. emply cells should also yield NaNs
    all_nan = read_csv(StringIO(default_na_cells + empty_cells),
                       names=names, dtype=dtypes)
    assert(all(np.isnan(all_nan.to_pandas()['float32'])))

    # no NA values: defaults are off, no custom values passed in
    # only NaNs should be empty cells
    none_nan = read_csv(StringIO(default_na_cells),
                        names=names, dtype=dtypes,
                        keep_default_na=False)
    assert(not any(np.isnan(none_nan.to_pandas()['float32'])))

    # na_filter off - only NaNs should be empty cells
    none_nan = read_csv(StringIO(default_na_cells + custom_na_cells),
                        names=names, dtype=dtypes,
                        na_filter=False, na_values=custom_na_values)
    assert(not any(np.isnan(none_nan.to_pandas()['float32'])))

    # custom NA values
    all_nan = read_csv(StringIO(all_cells),
                       names=names, dtype=dtypes,
                       na_values=custom_na_values)
    assert(all(np.isnan(all_nan.to_pandas()['float32'])))


def test_csv_reader_thousands(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file13.csv")

    names = dtypes = ["float32", "float64", "int32", "int64"]
    lines = [','.join(names),
             "1'234.5, 1'234.567, 1'234'567, 1'234'567'890",
             "12'345.6, 123'456.7, 12'345, 123'456'789"]

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    f32_ref = [1234.5, 12345.6]
    f64_ref = [1234.567, 123456.7]
    int32_ref = [1234567, 12345]
    int64_ref = [1234567890, 123456789]

    df = read_csv(str(fname), names=names, dtype=dtypes, skiprows=1,
                  thousands="'")

    np.testing.assert_allclose(f32_ref, df['float32'])
    np.testing.assert_allclose(f64_ref, df['float64'])
    np.testing.assert_allclose(int32_ref, df['int32'])
    np.testing.assert_allclose(int64_ref, df['int64'])


def test_csv_reader_buffer():

    names = dtypes = ["float32", "int32", "date"]
    lines = [','.join(names),
             "1234.5, 1234567, 11/22/1995",
             "12345.6, 12345, 1/2/2002"]

    buffer = '\n'.join(lines) + '\n'

    f32_ref = [1234.5, 12345.6]
    int32_ref = [1234567, 12345]

    df_str = read_csv(StringIO(buffer),
                      names=names, dtype=dtypes, skiprows=1)
    np.testing.assert_allclose(f32_ref, df_str['float32'])
    np.testing.assert_allclose(int32_ref, df_str['int32'])
    assert("1995-11-22T00:00:00.000" == str(df_str['date'][0]))
    assert("2002-01-02T00:00:00.000" == str(df_str['date'][1]))

    df_bytes = read_csv(BytesIO(str.encode(buffer)),
                        names=names, dtype=dtypes, skiprows=1)
    np.testing.assert_allclose(f32_ref, df_bytes['float32'])
    np.testing.assert_allclose(int32_ref, df_bytes['int32'])
    assert("1995-11-22T00:00:00.000" == str(df_bytes['date'][0]))
    assert("2002-01-02T00:00:00.000" == str(df_bytes['date'][1]))


def test_csv_reader_buffer_strings():

    names = ['text', 'int']
    dtypes = ['str', 'int']
    lines = [','.join(names), 'a,0', 'b,0', 'c,0', 'd,0']

    buffer = '\n'.join(lines) + '\n'

    cols_str = read_csv_strings(StringIO(buffer),
                                names=names, dtype=dtypes, skiprows=1)
    assert(len(cols_str) == 2)
    assert(type(cols_str[0]) == nvstrings.nvstrings)
    assert(type(cols_str[1]) == cudf.Series)
    assert(cols_str[0].sublist([0]).to_host()[0] == 'a')
    assert(cols_str[0].sublist([1]).to_host()[0] == 'b')
    assert(cols_str[0].sublist([2]).to_host()[0] == 'c')
    assert(cols_str[0].sublist([3]).to_host()[0] == 'd')

    cols_bytes = read_csv_strings(BytesIO(str.encode(buffer)),
                                  names=names, dtype=dtypes, skiprows=1)
    assert(len(cols_bytes) == 2)
    assert(type(cols_bytes[0]) == nvstrings.nvstrings)
    assert(type(cols_bytes[1]) == cudf.Series)
    assert(cols_bytes[0].sublist([0]).to_host()[0] == 'a')
    assert(cols_bytes[0].sublist([1]).to_host()[0] == 'b')
    assert(cols_bytes[0].sublist([2]).to_host()[0] == 'c')
    assert(cols_bytes[0].sublist([3]).to_host()[0] == 'd')


def test_csv_reader_gzip_compression(tmpdir):

    fname = tmpdir.mkdir("gdf_csv").join('tmp_csvreader_file10.csv.gz')

    df = make_datetime_dataframe()
    df.to_csv(fname, index=False, header=False, compression='gzip')

    df_out = pd.read_csv(fname, names=['col1', 'col2'], parse_dates=[0, 1],
                         dayfirst=True, compression='gzip')
    dtypes = ['date', 'date']
    out = read_csv(str(fname), names=list(df.columns.values), dtype=dtypes,
                   dayfirst=True, compression='gzip')

    assert len(out.columns) == len(df_out.columns)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())


@pytest.mark.parametrize('names, dtypes, data, trues, falses', [
    (['A', 'B'], ['int32', 'int32'], 'True,1\nFalse,2\nTrue,3', None, None),
    (['A', 'B'], ['int32', 'int32'], 'YES,1\nno,2\nyes,3\nNo,4\nYes,5',
        ["yes", "Yes", "YES"], ["no", "NO", "No"]),
    (['A', 'B'], ['int32', 'int32'], 'foo,bar\nbar,foo', ['foo'], ['bar'])
])
def test_csv_reader_bools(tmpdir, names, dtypes, data, trues, falses):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file11.csv")

    lines = [','.join(names), data]

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    # Usage of true_values and false_values makes that column into bool type
    df_out = pd.read_csv(fname, names=names, skiprows=1,
                         dtype=(dtypes[0] if dtypes else None),
                         true_values=trues, false_values=falses)

    out = read_csv(str(fname), names=names, dtype=dtypes, skiprows=1,
                   true_values=trues, false_values=falses)

    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())


def test_csv_quotednumbers(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file12.csv")

    names = ['integer', 'decimal']
    dtypes = ['int32', 'float32']
    lines = [','.join(names),
             '1,"3.14"', '"2","300"', '"3",10101.0101', '4,"6.28318"']

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    integer_ref = [1, 2, 3, 4]
    decimal_ref = [3.14, 300, 10101.0101, 6.28318]

    cols1 = read_csv(str(fname), names=names, dtype=dtypes, skiprows=1)
    cols2 = read_csv_strings(str(fname), names=names, dtype=dtypes, skiprows=1)

    assert(len(cols2) == 2)
    np.testing.assert_allclose(integer_ref, cols1['integer'])
    np.testing.assert_allclose(decimal_ref, cols1['decimal'])
    np.testing.assert_allclose(integer_ref, cols2[0])
    np.testing.assert_allclose(decimal_ref, cols2[1])


def test_csv_reader_nrows(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file14.csv")

    names = ["int1", "int2"]
    dtypes = ["int32", "int32"]

    rows = 4000000
    read_rows = (rows*3)//4
    skip_rows = (rows - read_rows)//2
    sample_skip = 1000

    with open(str(fname), 'w') as fp:
        fp.write(','.join(names) + '\n')
        for i in range(rows):
            fp.write(str(i) + ', ' + str(2*i) + ' \n')

    # with specified names
    df = read_csv(str(fname),
                  names=names, dtype=dtypes,
                  skiprows=skip_rows + 1, nrows=read_rows)
    assert(df.shape == (read_rows, 2))
    for row in range(0, read_rows//sample_skip, sample_skip):
        assert(df['int1'][row] == row + skip_rows)
        assert(df['int2'][row] == 2 * (row + skip_rows))
    assert(df['int2'][read_rows - 1] == 2 * (read_rows - 1 + skip_rows))

    # with column name inference
    df = read_csv(str(fname),
                  dtype=dtypes,
                  skiprows=skip_rows + 1, nrows=read_rows)
    assert(df.shape == (read_rows, 2))
    assert(str(skip_rows) in list(df)[0])
    assert(str(2*skip_rows) in list(df)[1])
    for row in range(0, read_rows//sample_skip, sample_skip):
        assert(df[list(df)[0]][row] == row + skip_rows + 1)
        assert(df[list(df)[1]][row] == 2 * (row + skip_rows + 1))
    assert(df[list(df)[1]][read_rows - 1] == 2 * (read_rows + skip_rows))

    # nrows larger than the file
    df = read_csv(str(fname),
                  dtype=dtypes, nrows=rows*2)
    assert(df.shape == (rows, 2))
    for row in range(0, rows//sample_skip, sample_skip):
        assert(df['int1'][row] == row)
        assert(df['int2'][row] == 2 * row)
    assert(df['int2'][rows - 1] == 2 * (rows - 1))

    # nrows + skiprows larger than the file
    df = read_csv(str(fname),
                  dtype=dtypes, nrows=read_rows, skiprows=read_rows)
    assert(df.shape == (rows - read_rows, 2))

    # nrows equal to zero
    df = read_csv(str(fname),
                  dtype=dtypes,
                  nrows=0)
    assert(df.shape == (0, 2))

    # with both skipfooter and nrows - should throw
    with pytest.raises(ValueError):
        read_csv(str(fname),
                 nrows=read_rows, skipfooter=1)


def test_csv_reader_gzip_compression_strings(tmpdir):
    fnamebase = tmpdir.mkdir("gdf_csv")
    fname = fnamebase.join("tmp_csvreader_file15.csv")
    fnamez = fnamebase.join("tmp_csvreader_file15.csv.gz")

    names = ['text', 'int']
    dtypes = ['str', 'int']
    lines = [','.join(names), 'a,0', 'b,0', 'c,0', 'd,0']

    with open(str(fname), 'w') as fp:
        fp.write('\n'.join(lines) + '\n')

    with open(str(fname), 'rb') as f_in, gzip.open(str(fnamez), 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

    cols = read_csv_strings(str(fnamez), names=names, dtype=dtypes, skiprows=1,
                            decimal='.', thousands="'", compression='gzip')

    assert(len(cols) == 2)
    assert(type(cols[0]) == nvstrings.nvstrings)
    assert(type(cols[1]) == cudf.Series)
    assert(cols[0].sublist([0]).to_host()[0] == 'a')
    assert(cols[0].sublist([1]).to_host()[0] == 'b')
    assert(cols[0].sublist([2]).to_host()[0] == 'c')
    assert(cols[0].sublist([3]).to_host()[0] == 'd')


@pytest.mark.parametrize('skip_rows', [0, 2, 4])
@pytest.mark.parametrize('header_row', [0, 2])
def test_csv_reader_skiprows_header(skip_rows, header_row):

    names = ['float_point', 'integer']
    dtypes = ['float64', 'int64']
    lines = [','.join(names),
             '1.2, 1',
             '2.3, 2',
             '3.4, 3',
             '4.5, 4',
             '5.6, 5',
             '6.7, 6']
    buffer = '\n'.join(lines) + '\n'

    cu_df = read_csv(StringIO(buffer), dtype=dtypes,
                     skiprows=skip_rows, header=header_row)
    pd_df = pd.read_csv(StringIO(buffer),
                        skiprows=skip_rows, header=header_row)

    assert(cu_df.shape == pd_df.shape)
    assert(list(cu_df.columns.values) == list(pd_df.columns.values))


def test_csv_reader_dtype_inference():
    names = ['float_point', 'integer']
    lines = [','.join(names),
             '1.2,1',
             '2.3,2',
             '3.4,3',
             '4.5,4',
             '5.6,5',
             '6.7,6']
    buffer = '\n'.join(lines) + '\n'
    cu_df = read_csv(StringIO(buffer))
    pd_df = pd.read_csv(StringIO(buffer))

    assert(cu_df.shape == pd_df.shape)
    assert(list(cu_df.columns.values) == list(pd_df.columns.values))


def test_csv_reader_dtype_inference_whitespace():
    names = ['float_point', 'integer']
    lines = [','.join(names),
             '  1.2,    1',
             '2.3,2    ',
             '  3.4,   3',
             ' 4.5,4',
             '5.6,  5',
             ' 6.7,6 ']
    buffer = '\n'.join(lines) + '\n'
    cu_df = read_csv(StringIO(buffer))
    pd_df = pd.read_csv(StringIO(buffer))

    assert(cu_df.shape == pd_df.shape)
    assert(list(cu_df.columns.values) == list(pd_df.columns.values))


def test_csv_reader_empty_dataframe():

    dtypes = ['float64', 'int64']
    buffer = 'float_point, integer\n'

    # should work fine with dtypes
    df = read_csv(StringIO(buffer), dtype=dtypes)
    assert(df.shape == (0, 2))

    # should raise an error without dtypes
    with pytest.raises(GDFError):
        read_csv(StringIO(buffer))


def test_csv_reader_filenotfound(tmpdir):
    fname = "non-existing-filename.csv"

    # should raise an error
    with pytest.raises(FileNotFoundError):
        read_csv(str(fname))

    # should raise an error
    dname = tmpdir.mkdir("gdf_csv")
    with pytest.raises(FileNotFoundError):
        read_csv(str(dname))


def test_csv_reader_carriage_return(tmpdir):

    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file16.csv")

    rows = 1000

    with open(str(fname), 'w') as fp:
        for i in range(rows):
            fp.write(str(i) + ', ' + str(2*i) + '\r\n')

    df = read_csv(str(fname), names=["int1", "int2"])

    assert(len(df) == rows)
    for row in range(0, rows):
        assert(df['int1'][row] == row)
        assert(df['int2'][row] == 2 * row)


def test_csv_reader_bzip2_compression(tmpdir):
    fname = tmpdir.mkdir("gdf_csv").join('tmp_csvreader_file16.csv.bz2')

    df = make_datetime_dataframe()
    df.to_csv(fname, index=False, header=False, compression='bz2')

    df_out = pd.read_csv(fname, names=['col1', 'col2'], parse_dates=[0, 1],
                         dayfirst=True, compression='bz2')
    dtypes = ['date', 'date']
    out = read_csv(str(fname), names=list(df.columns.values), dtype=dtypes,
                   dayfirst=True, compression='bz2')

    assert len(out.columns) == len(df_out.columns)
    pd.util.testing.assert_frame_equal(df_out, out.to_pandas())


def test_csv_reader_tabs():
    names = ['float_point', 'integer', 'date']
    lines = [','.join(names),
             '1.2,\t12,     \t11/22/1995',
             '3.4\t,\t34\t,\t 01/01/2001',
             '\t 5.6,56 \t, 12/12/1970',
             '\t7.8 , 78\t,06/15/2018 \t']
    buffer = '\n'.join(lines) + '\n'

    df = read_csv(StringIO(buffer))

    assert(df.shape == (4, 3))

    floats = [1.2, 3.4, 5.6, 7.8]
    ints = [12, 34, 56, 78]
    dates = ['1995-11-22T00:00:00.000',
             '2001-01-01T00:00:00.000',
             '1970-12-12T00:00:00.000',
             '2018-06-15T00:00:00.000']
    np.testing.assert_allclose(floats, df['float_point'])
    np.testing.assert_allclose(ints, df['integer'])
    for row in range(4):
        assert(str(df['date'][row]) == dates[row])


@pytest.mark.parametrize('segment_bytes', [10000, 19999, 30001, 36000])
def test_csv_reader_byte_range(tmpdir, segment_bytes):
    fname = tmpdir.mkdir("gdf_csv").join("tmp_csvreader_file16.csv")

    names = ['int1', 'int2']

    rows = 10000
    with open(str(fname), 'w') as fp:
        for i in range(rows):
            fp.write(str(i) + ', ' + str(2*i) + ' \n')
    file_size = os.stat(str(fname)).st_size

    ref_df = read_csv(str(fname), names=names).to_pandas()

    dfs = []
    for segment in range((file_size + segment_bytes - 1)//segment_bytes):
        dfs.append(read_csv(str(fname), names=names,
                   byte_range=(segment*segment_bytes, segment_bytes)))
    df = cudf.concat(dfs).to_pandas()

    assert(list(df['int1']) == list(ref_df['int1']))
    assert(list(df['int2']) == list(ref_df['int2']))


@pytest.mark.parametrize('header_row, skip_rows, skip_blanks',
                         [(1, 0, True), ('infer', 2, True), (1, 4, True),
                          (3, 0, False), ('infer', 5, False)])
def test_csv_reader_blanks_and_comments(skip_rows, header_row, skip_blanks):

    lines = ['# first comment line',
             '\n',
             '# third comment line',
             '1,2,3',
             '4,5,6',
             '7,8,9',
             '\n',
             '# last comment line'
             '\n',
             '1,1,1']
    buffer = '\n'.join(lines) + '\n'

    cu_df = read_csv(StringIO(buffer), comment='#', header=header_row,
                     skiprows=skip_rows, skip_blank_lines=skip_blanks)
    pd_df = pd.read_csv(StringIO(buffer), comment='#', header=header_row,
                        skiprows=skip_rows, skip_blank_lines=skip_blanks)

    assert(cu_df.shape == pd_df.shape)
    assert(list(cu_df.columns.values) == list(pd_df.columns.values))


def test_csv_reader_prefix():

    lines = ['1, 1, 1, 1']
    buffer = '\n'.join(lines) + '\n'

    prefix_str = 'a_prefix'
    df = read_csv(StringIO(buffer), header=None, prefix=prefix_str)

    column_names = list(df.columns.values)
    for col in range(len(column_names)):
        assert(column_names[col] == prefix_str + str(col))


def test_csv_reader_category_hash():

    lines = ['HBM0676', 'KRC0842', 'ILM1441', 'EJV0094', 'ILM1441']
    buffer = '\n'.join(lines) + '\n'

    df = read_csv(StringIO(buffer), names=['user'], dtype=['category'])

    hash_ref = [2022314536, -189888986, 1512937027, 397836265, 1512937027]
    assert(list(df['user']) == hash_ref)


def test_csv_reader_delim_whitespace():
    buffer = '1    2  3\n4  5 6\n'

    # with header row
    cu_df = read_csv(StringIO(buffer), delim_whitespace=True)
    pd_df = pd.read_csv(StringIO(buffer), delim_whitespace=True)
    pd.util.testing.assert_frame_equal(pd_df, cu_df.to_pandas())

    # without header row
    cu_df = read_csv(StringIO(buffer), delim_whitespace=True, header=None)
    pd_df = pd.read_csv(StringIO(buffer), delim_whitespace=True, header=None)
    assert(pd_df.shape == cu_df.shape)

    # should raise an error if used with delimiter or sep
    with pytest.raises(ValueError):
        read_csv(StringIO(buffer), delim_whitespace=True, delimiter=' ')
    with pytest.raises(ValueError):
        read_csv(StringIO(buffer), delim_whitespace=True, sep=' ')


def test_csv_reader_unnamed_cols():
    # first and last columns are unnamed
    buffer = ',1,2,3,\n4,5,6,7,8\n'

    cu_df = read_csv(StringIO(buffer))
    pd_df = pd.read_csv(StringIO(buffer))

    assert(all(pd_df.columns == cu_df.columns))
    assert(pd_df.shape == cu_df.shape)


def test_csv_reader_header_quotation():
    buffer = '"1,,1","2,\n,2",3\n4,5,6\n'

    cu_df = read_csv(StringIO(buffer))
    pd_df = pd.read_csv(StringIO(buffer))
    assert(cu_df.shape == (1, 3))
    pd.util.testing.assert_frame_equal(pd_df, cu_df.to_pandas())

    # test cases that fail with pandas
    buffer_pd_fail = '"1,one," , ",2,two" ,3\n4,5,6\n'
    cu_df = read_csv(StringIO(buffer_pd_fail))
    assert(cu_df.shape == (1, 3))


def test_csv_reader_oversized_byte_range():
    buffer = 'a,b,c,d,e\n4,5,6,7,8\n'

    cu_df = read_csv(StringIO(buffer), byte_range=(0, 1024))
    pd_df = pd.read_csv(StringIO(buffer))

    assert(all(pd_df.columns == cu_df.columns))
    assert(pd_df.shape == cu_df.shape)


def test_csv_reader_index_col():
    buffer = '0,1,2\n3,4,5\n6,7,8\n'
    names = ['int1', 'int2', 'int3']

    # using a column name
    cu_df = read_csv(StringIO(buffer), names=names, index_col='int1')
    pd_df = pd.read_csv(StringIO(buffer), names=names, index_col='int1')
    pd.util.testing.assert_frame_equal(pd_df, cu_df.to_pandas())

    # using a column index
    cu_df = read_csv(StringIO(buffer), header=None, index_col=0)
    pd_df = pd.read_csv(StringIO(buffer), header=None, index_col=0)
    for cu_idx, pd_idx in zip(cu_df.index, pd_df.index):
        assert(str(cu_idx) == str(pd_idx))

    # passing False to avoid using a column as index (no-op in cuDF)
    cu_df = read_csv(StringIO(buffer), header=None, index_col=False)
    pd_df = pd.read_csv(StringIO(buffer), header=None, index_col=False)
    for cu_idx, pd_idx in zip(cu_df.index, pd_df.index):
        assert(str(cu_idx) == str(pd_idx))


def test_csv_reader_bools_false_positives(tmpdir):
    # values that are equal to ["True", "TRUE", "False", "FALSE"]
    # when using ints to detect bool values
    items = [3977, 4329, 24015, 27567]

    buffer = '\n'.join(str(i) for i in items) + '\n'

    df = read_csv(StringIO(buffer),
                  header=None, dtype=["int32"])

    np.testing.assert_array_equal(items, df['0'])
