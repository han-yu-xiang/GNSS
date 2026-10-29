function tests = test_sha256_file_streaming
tests = functiontests(localfunctions);
end

function testPreservesHighBitBytes(testCase)
path = [tempname, '.bin'];
cleanup = onCleanup(@() deleteIfPresent(path)); %#ok<NASGU>
fileId = fopen(path, 'wb');
assert(fileId >= 0, 'Unable to create SHA-256 test fixture.');
fileCleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
fwrite(fileId, uint8([0, 127, 128, 255]), 'uint8');
clear fileCleanup

actual = sha256_file_streaming(path);
testCase.verifyEqual(actual, ...
    '89273d2f70b93285bb7ddb4bcee86a5347ca7159352e3cbdd20c23e9d1e507d3');
end

function deleteIfPresent(path)
if isfile(path)
    delete(path);
end
end
