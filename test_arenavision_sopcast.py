import datetime
import arenavision_sopcast


def test_parse_schedule_row():
    row = "11/05/16 11:00 CET TENIS: MASTER 1000 DE ROMA (ATP WORLD TOUR)/AV19/AV20/AV35/AV36"
    item = arenavision_sopcast.parse_schedule_row(row)

    expected = (datetime.datetime(2016, 5, 11, 11, 0), 'TENIS', 'MASTER 1000 DE ROMA', 'ATP WORLD TOUR',
                ['AV19', 'AV20', 'AV35', 'AV36'])

    assert item == expected


# this will not be executed automatically.
def auxiliar_parse_row_expect_none(row):
    item = arenavision_sopcast.parse_schedule_row(row)

    assert item is None


# if a date comes incomplete, we don't want this item
def test_parse_schedule_row_bad_date():
    row = "/05/16 11:00 CET TENIS: MASTER 1000 DE ROMA (ATP WORLD TOUR)/AV19/AV20/AV35/AV36"
    auxiliar_parse_row_expect_none(row)


# if a sport is not parseable, we don't want this item
def test_parse_schedule_row_bad_sport():
    row = "11/05/16 11:00 C TENIS: MASTER 1000 DE ROMA (ATP WORLD TOUR)/AV19/AV20/AV35/AV36"
    auxiliar_parse_row_expect_none(row)


# if a description is not found, we don't want this item
def test_parse_schedule_row_bad_description():
    row = "11/05/16 11:00 CET TENIS: /AV19/AV20/AV35/AV36"
    auxiliar_parse_row_expect_none(row)


# if a row has no channels... this should be skipped... (TODO)
def test_parse_schedule_row_no_channels():
    row = "11/05/16 11:00 CET TENIS: MASTER 1000 DE ROMA (ATP WORLD TOUR)/"
    item = arenavision_sopcast.parse_schedule_row(row)

    expected = (datetime.datetime(2016, 5, 11, 11, 0), 'TENIS', 'MASTER 1000 DE ROMA', 'ATP WORLD TOUR',[])

    assert item == expected


# test option_chooser
# TODO: check output header, output and items list
# TODO: check output if input is a keyword
# TODO: check output if input is a channel
def option_chooser():
    header = "This is a header and should be written"
    choose = "This string should be printed too"
    arenavision_sopcast.option_chooser(options=[[1, "pepe"], [2, "juan"], [3,"pedro"]], header=header, choose=choose, allowfilter=True)


# test Item class
def mock_item_data():
    # return arenavision_sopcast.Item([datetime.datetime(2016, 01, 01, 00, 00), "FUTBOL", "BARCA - MADRID", "LA LIGA", ["av21", "av22"]])
    return [datetime.datetime(2016, 1, 1, 0, 0), "FUTBOL", "BARCA - MADRID", "LA LIGA", ["av21", "av22"]]


def test_item_gettime():
    item = arenavision_sopcast.Item(mock_item_data())
    assert item.gettime() == mock_item_data()[0].strftime(arenavision_sopcast.DATEFORMAT)


def test_item_header():
    data = mock_item_data()
    item = arenavision_sopcast.Item(data)
    assert item.header() == "\n".join([data[1] + " - " + data[3], data[0].strftime(arenavision_sopcast.DATEFORMAT) + " " + data[2]])


def test_item_tolist():
    data = mock_item_data()
    item = arenavision_sopcast.Item(data)
    assert item.tolist() == [
        data[0].strftime(arenavision_sopcast.DATEFORMAT),
        data[1].decode("utf8"),data[3].decode("utf8"), data[2].decode("utf8")
    ]


def test_item_matches():
    data = mock_item_data()
    item = arenavision_sopcast.Item(data)
    assert item.matches(("barc",))
