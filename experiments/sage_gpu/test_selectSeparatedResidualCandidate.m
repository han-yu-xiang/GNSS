function tests = test_selectSeparatedResidualCandidate
tests = functiontests(localfunctions);
end

function testRejectsTopSeparatedCandidateAndRetriesNextValid(testCase)
delays = [2, 3, 4];
dopplers = [-5401.1462447797148, -5301.1462447797148];
metric = [100, 1; 80, 0; 90, 0];
existingDelays = [0.7, 2.7];

[candidate, trace] = selectSeparatedResidualCandidate( ...
    delays, dopplers, metric, existingDelays, 1.0);

verifyEqual(testCase, candidate.delaySamples, 4);
verifyEqual(testCase, candidate.dopplerHz, dopplers(1));
verifyEqual(testCase, candidate.score, 90);
verifyEqual(testCase, [trace.candidate_rank], [1, 2]);
verifyEqual(testCase, [trace.candidate_delay], [2, 4]);
verifyEqual(testCase, [trace.accepted], [false, true]);
verifyEqual(testCase, trace(1).rejection_reason, "REJECT_SEPARATION");
verifyEqual(testCase, trace(2).rejection_reason, "ACCEPTED");
verifyEqual(testCase, trace(1).min_separation_to_existing_paths, 0.7, ...
    "AbsTol", 1e-12);
verifyEqual(testCase, trace(2).min_separation_to_existing_paths, 1.3, ...
    "AbsTol", 1e-12);
end

function testUsesProductionTieRemovalAndColumnMajorMaxOrder(testCase)
delays = [0, 2, 3];
dopplers = [-10, 10];
metric = [10, 1; 10, 0; 9, 0];

[candidate, trace] = selectSeparatedResidualCandidate( ...
    delays, dopplers, metric, 0, 1.0);

% Production removes every exact current maximum after rejecting the first.
% Thus the tied, otherwise-separated delay 2 is removed with the rejected tie.
verifyEqual(testCase, candidate.delaySamples, 3);
verifyEqual(testCase, [trace.candidate_delay], [0, 3]);
verifyEqual(testCase, [trace.candidate_rank], [1, 3]);
verifyEqual(testCase, [trace.accepted], [false, true]);
verifyEqual(testCase, trace(1).min_separation_to_existing_paths, 0);
end

function testMinimumSeparationBoundaryIsInclusive(testCase)
[candidate, trace] = selectSeparatedResidualCandidate( ...
    2, -4, 7, 1, 1.0);

verifyEqual(testCase, candidate.delaySamples, 2);
verifyEqual(testCase, trace.min_separation_to_existing_paths, 1);
verifyTrue(testCase, trace.accepted);
end

function testExhaustionUsesProductionError(testCase)
thrown = false;
try
    selectSeparatedResidualCandidate([2, 3], 0, [2; 1], 2.5, 1.0);
catch exception
    thrown = true;
verifyEqual(testCase, exception.message, ...
        'No separated residual path could be initialized.');
end
verifyTrue(testCase, thrown, "Expected production exhaustion error.");
end
