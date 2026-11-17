def encode_ics(lines):
    """RFC 5545 CRLF, UTF-8 and line folding without splitting a code point."""
    result=[]
    for line in lines:
        part=''
        for char in line:
            if len((part+char).encode('utf-8'))>75:
                result.append(part);part=' '
            part+=char
        result.append(part)
    return ('\r\n'.join(result)+'\r\n').encode('utf-8')
