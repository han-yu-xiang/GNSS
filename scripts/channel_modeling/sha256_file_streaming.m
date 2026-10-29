function digest = sha256_file_streaming(path)
%SHA256_FILE_STREAMING Compute SHA-256 without changing unsigned byte values.
fileId = fopen(path, 'rb');
assert(fileId >= 0, 'GNSS:SAGE:Sha256FileReadFailed', ...
    'Cannot read file for SHA-256: %s.', path);
cleanup = onCleanup(@() fclose(fileId));
messageDigest = java.security.MessageDigest.getInstance('SHA-256');
while true
    bytes = fread(fileId, 4 * 1024 * 1024, '*uint8');
    if isempty(bytes)
        break
    end
    % int8(uint8) saturates values above 127. typecast preserves the bit
    % pattern required by Java's signed-byte array API.
    messageDigest.update(typecast(bytes, 'int8'));
end
digestBytes = typecast(messageDigest.digest(), 'uint8');
digest = lower(reshape(dec2hex(digestBytes, 2).', 1, []));
end
