function tests = test_code_domain_cir_snapshot
tests = functiontests(localfunctions);
end

function testNavAndCarrierWipePreserveRawAmplitude(testCase)
sampleCount = 1024;
localCode = ones(sampleCount, 1);
localCode(2:2:end) = -1;
navSigns = -ones(sampleCount, 1);
samplingRateHz = 10230000;
carrierHz = -2137.25;
timeOffsetS = 0.017;
sampleTimeS = timeOffsetS + (0:sampleCount - 1).' / samplingRateHz;
signal = 3.25 * localCode .* exp(1j * 2 * pi * carrierHz * sampleTimeS);
rawIq = navSigns .* signal;

[cir, rawRms] = compute_gnss_code_domain_cir_snapshot( ...
    rawIq, localCode, 0, samplingRateHz, carrierHz, ...
    timeOffsetS, navSigns);

testCase.verifyEqual(real(cir(1)), 3.25, 'AbsTol', 2e-6);
testCase.verifyEqual(imag(cir(1)), 0, 'AbsTol', 2e-6);
testCase.verifyEqual(rawRms, 3.25, 'AbsTol', 1e-12);
end

function testCorrelationUsesFrozenSageDelaySign(testCase)
sampleCount = 1024;
rng(17, 'twister');
localCode = 2 * double(rand(sampleCount, 1) > 0.5) - 1;
rawIq = circshift(localCode, 3);

[cir, ~] = compute_gnss_code_domain_cir_snapshot( ...
    rawIq, localCode, [3, 0], 10230000, 0, 0, ...
    ones(sampleCount, 1));

testCase.verifyGreaterThan(abs(cir(1)), abs(cir(2)));
testCase.verifyGreaterThan(real(cir(1)), 0.9);
end
