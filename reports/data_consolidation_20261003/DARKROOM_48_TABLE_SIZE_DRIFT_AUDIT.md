# Darkroom 48-table collection size-drift audit

Audit date: 2026-10-03
Scope: metadata, directory inventory, manifests, QA, README, and SHA-256 verification of the 48 table files. No table was regenerated; no raw IQ was read; no MATLAB, SAGE, GNSS-SDR, or batch was run.

## Conclusion

DARKROOM_48_TABLE_INTEGRITY=PASS
SIZE_DRIFT=BENIGN_METADATA_ADDITION

The reported 111,016-byte difference is a scope mismatch: the earlier handoff's 14,151,548,683-byte figure is the sum of the 48 formal table files. The current recursive directory size is 14,151,659,699 bytes because it also includes nine small README/manifest/QA/provenance/receipt/log/lock files totaling exactly 111,016 bytes. There are no hidden files in the collection. The 48 table files are intact and their current SHA-256 values match both generation_manifest.csv and qa_summary.csv (48/48).

## Inventory and provenance

- Formal tables: 48 files; 14,151,548,683 bytes; each is listed below.
- All files recursively under the collection: 57 files; 14,151,659,699 bytes.
- Non-table support files: 9 files; 111,016 bytes.
- Collection manifest SHA-256: bfe45c8d7691d48a99dbd3f9c8ff6231f86814264135be1060d6527d6256a749; matches the adjacent collection_manifest.sha256 and the current engineering handoff.
- Generation manifest SHA-256: 9089085522308b3dbeb202eced7ae553f7673178df7aa8f42e60babe34b9c23c.
- Collection QA: PASS, 48/48 tables, 172,800,000 total rows; current collection_qa_report.json SHA-256 0976d62784faa2a00ed333db7878db58e90d5262f1cb290e8063448b4320ef1f.
- Current qa_summary.csv SHA-256: a27f5396b354a2c8edeed95801bb03b41c4012c9873b74934e1239bd4764b1ae.
- README describes the 48-table isolated collection and points to manifest/SHA evidence; it is retained.
- The 111,016 bytes are not additional table payload: the 9 files are metadata/provenance or QA/log artifacts. One is a released-lock record; none are hidden files.

### Non-table files included in the recursive directory size

| Relative path | Bytes |
|---|---:|
| collection_qa_report.json | 596 |
| generation_manifest.csv | 30,425 |
| provenance/.collection.active.released.darkroom_5min_multiseed_48_20260915.1789455901929697200.lock | 197 |
| provenance/collection_generation_receipt.json | 538 |
| provenance/collection_manifest.json | 50,270 |
| provenance/collection_manifest.sha256 | 91 |
| provenance/generation_progress.jsonl | 17,662 |
| qa_summary.csv | 10,348 |
| README.md | 889 |

### All 48 formal tables

| Filename | Bytes | Generation-manifest SHA-256 | QA SHA-256 | Current hash check |
|---|---:|---|---|---|
| highway_open__good__01.csv | 295,738,571 | 6d58847b244080348709a9a36ca6d7fdb8b78f82a95eb4e42e377097f07f7a85 | 6d58847b244080348709a9a36ca6d7fdb8b78f82a95eb4e42e377097f07f7a85 | MATCH |
| highway_open__good__02.csv | 295,437,359 | a5a90ad9c7d2e0b94fdb46ef0d229623173fc8516ff972b311983e0cd5c9d135 | a5a90ad9c7d2e0b94fdb46ef0d229623173fc8516ff972b311983e0cd5c9d135 | MATCH |
| highway_open__good__03.csv | 294,843,992 | db228558d066a96fe7ad5d3c7be674ed1e1a33ea5db1194f04e0e1e4d4e9ecfb | db228558d066a96fe7ad5d3c7be674ed1e1a33ea5db1194f04e0e1e4d4e9ecfb | MATCH |
| highway_open__good__04.csv | 295,426,678 | 4a758d42bec9d8491be5d4f51dd10ebd6b5efd30c42bba86b926a5e987f8d66d | 4a758d42bec9d8491be5d4f51dd10ebd6b5efd30c42bba86b926a5e987f8d66d | MATCH |
| highway_open__poor__01.csv | 295,744,734 | e8e747a74e9eabce73238abcc1ea231810bb502cb0729688c261cb9a871c6953 | e8e747a74e9eabce73238abcc1ea231810bb502cb0729688c261cb9a871c6953 | MATCH |
| highway_open__poor__02.csv | 295,441,018 | 4dadd691182d3f6a750ebe1a404378dd20ac8203765fcf46e7c2bd3be0edeaa9 | 4dadd691182d3f6a750ebe1a404378dd20ac8203765fcf46e7c2bd3be0edeaa9 | MATCH |
| highway_open__poor__03.csv | 294,848,102 | 29e11efc5f670b3a0fb38fb47bd184ebfcc3b9abb3c184094327dcdc56a736c0 | 29e11efc5f670b3a0fb38fb47bd184ebfcc3b9abb3c184094327dcdc56a736c0 | MATCH |
| highway_open__poor__04.csv | 295,436,836 | ab806ba4c87aa7374a1e82f83a782ed927e9fec128e764ced629df8a3d2aa87d | ab806ba4c87aa7374a1e82f83a782ed927e9fec128e764ced629df8a3d2aa87d | MATCH |
| highway_open__rain__01.csv | 293,484,229 | 09c368476afdb98891a1505e1249ce03d54db82d8ad525fcd4730e01ace10b87 | 09c368476afdb98891a1505e1249ce03d54db82d8ad525fcd4730e01ace10b87 | MATCH |
| highway_open__rain__02.csv | 293,505,151 | 95a521373264cfb16045d1bef208aa364dd493c06e3b5bfadeb576bea05fc359 | 95a521373264cfb16045d1bef208aa364dd493c06e3b5bfadeb576bea05fc359 | MATCH |
| highway_open__rain__03.csv | 292,907,653 | d5a8a165460935c319bfd57ace6cc26856cf2f96b64d324c29398cd7aebbfb79 | d5a8a165460935c319bfd57ace6cc26856cf2f96b64d324c29398cd7aebbfb79 | MATCH |
| highway_open__rain__04.csv | 293,800,397 | 851c34d51b9a4aa62b9c55264ea71ed2bd2c1f5790e66419192966ba1838eae8 | 851c34d51b9a4aa62b9c55264ea71ed2bd2c1f5790e66419192966ba1838eae8 | MATCH |
| mountain_valley__good__01.csv | 296,461,459 | 729b6231c3c58f9949a786dd1fa9c0ef02800922ae568eaf9fe8756665d6d8cb | 729b6231c3c58f9949a786dd1fa9c0ef02800922ae568eaf9fe8756665d6d8cb | MATCH |
| mountain_valley__good__02.csv | 296,449,102 | 818f1442f443964e40bfde371eb4712d779452b0ec1cd4dfbabe82b4056d4b67 | 818f1442f443964e40bfde371eb4712d779452b0ec1cd4dfbabe82b4056d4b67 | MATCH |
| mountain_valley__good__03.csv | 295,824,367 | 743b2dec391e22ff6330c77b448fea66d9b68229820183623e5247a73e1a91ae | 743b2dec391e22ff6330c77b448fea66d9b68229820183623e5247a73e1a91ae | MATCH |
| mountain_valley__good__04.csv | 295,457,316 | f75cf27d604b989d822d9c0b00d0283e351942509878327837f04ffac840207a | f75cf27d604b989d822d9c0b00d0283e351942509878327837f04ffac840207a | MATCH |
| mountain_valley__poor__01.csv | 296,482,229 | b8061795cf280284b0c600f994f23f4328290896918dd2a7b4c162187e555b44 | b8061795cf280284b0c600f994f23f4328290896918dd2a7b4c162187e555b44 | MATCH |
| mountain_valley__poor__02.csv | 296,457,724 | 1bc0841fb087475d4c77e04d07b204f428bca88866f0948e31525f324d3da54d | 1bc0841fb087475d4c77e04d07b204f428bca88866f0948e31525f324d3da54d | MATCH |
| mountain_valley__poor__03.csv | 295,847,521 | c9eab86b760027fa9c1a3db58a3ccd77d7818f485100b432626eb2c6c3d85e43 | c9eab86b760027fa9c1a3db58a3ccd77d7818f485100b432626eb2c6c3d85e43 | MATCH |
| mountain_valley__poor__04.csv | 295,479,645 | 4de0816cad474a72f6672fa637bf203906a9b4c948047f42905c9265a686bdc3 | 4de0816cad474a72f6672fa637bf203906a9b4c948047f42905c9265a686bdc3 | MATCH |
| mountain_valley__rain__01.csv | 293,795,960 | 6ccf3fbd38a6bcf925821c44e769bb12966b37631f051aeadeba3b4d97f7ffd1 | 6ccf3fbd38a6bcf925821c44e769bb12966b37631f051aeadeba3b4d97f7ffd1 | MATCH |
| mountain_valley__rain__02.csv | 293,709,415 | 7279faf7e8b07774810b217a706c4828d1c629812a55e9faedb958d10b48ebb2 | 7279faf7e8b07774810b217a706c4828d1c629812a55e9faedb958d10b48ebb2 | MATCH |
| mountain_valley__rain__03.csv | 293,466,626 | 940cf90a3264c8af506a2d1b9704ebfb8cce5d56b80e1243b770f655a9cc4a09 | 940cf90a3264c8af506a2d1b9704ebfb8cce5d56b80e1243b770f655a9cc4a09 | MATCH |
| mountain_valley__rain__04.csv | 293,032,910 | 8c354182df2892671a8e8750358976a62f0c50523871902da3ae1adb349f886c | 8c354182df2892671a8e8750358976a62f0c50523871902da3ae1adb349f886c | MATCH |
| special_reflective__good__01.csv | 296,140,479 | cc95c2342ef1a8ca4f80baf48f5ee701f2ba1c1f3067ddd5e7371b0c67086af2 | cc95c2342ef1a8ca4f80baf48f5ee701f2ba1c1f3067ddd5e7371b0c67086af2 | MATCH |
| special_reflective__good__02.csv | 295,561,325 | c1c68a409a082b0a659f1378cc30ae4e7d043b456686cc7a36c907e37c311eee | c1c68a409a082b0a659f1378cc30ae4e7d043b456686cc7a36c907e37c311eee | MATCH |
| special_reflective__good__03.csv | 295,833,037 | 9b733bcaebfa7425f7047784c7a5b9816b64cbbd5cf23d78c49ff925629a94f6 | 9b733bcaebfa7425f7047784c7a5b9816b64cbbd5cf23d78c49ff925629a94f6 | MATCH |
| special_reflective__good__04.csv | 296,148,951 | b2b8970ec4510a4651090d41b7fbdd30c9ecb8dd1c3a3441eba58eca25fe4df6 | b2b8970ec4510a4651090d41b7fbdd30c9ecb8dd1c3a3441eba58eca25fe4df6 | MATCH |
| special_reflective__poor__01.csv | 296,142,424 | 3b40225963461100a8e5617b58e8823646df2424409689cdd3027421d4769724 | 3b40225963461100a8e5617b58e8823646df2424409689cdd3027421d4769724 | MATCH |
| special_reflective__poor__02.csv | 295,564,383 | c5cad7e8b3b22e939ef0c33d02eb72dd05f124fd8ec0335ef75736cf8f7bb5fe | c5cad7e8b3b22e939ef0c33d02eb72dd05f124fd8ec0335ef75736cf8f7bb5fe | MATCH |
| special_reflective__poor__03.csv | 295,840,876 | 6708793a8628ff772ad541b2e918d808fc8a3f888055e537816beff60d79e87d | 6708793a8628ff772ad541b2e918d808fc8a3f888055e537816beff60d79e87d | MATCH |
| special_reflective__poor__04.csv | 296,155,152 | 26d27ff71401c60121f42cc08359807f45e8329771506524d2be0d858fee5d1e | 26d27ff71401c60121f42cc08359807f45e8329771506524d2be0d858fee5d1e | MATCH |
| special_reflective__rain__01.csv | 293,036,660 | 92647090171a483ce73c4ac10bcd18bcf8d0fc1af995e9d1efef6bc4644251da | 92647090171a483ce73c4ac10bcd18bcf8d0fc1af995e9d1efef6bc4644251da | MATCH |
| special_reflective__rain__02.csv | 293,357,284 | 110a48d4cd7e5081e1781078f86ca2f273ab282b99b3b403db9370c6f9d443bc | 110a48d4cd7e5081e1781078f86ca2f273ab282b99b3b403db9370c6f9d443bc | MATCH |
| special_reflective__rain__03.csv | 292,728,169 | 0f30b4c5d8324a5221ff7d6703b33bd39b2b2e4e83b18eee869c518eeb261026 | 0f30b4c5d8324a5221ff7d6703b33bd39b2b2e4e83b18eee869c518eeb261026 | MATCH |
| special_reflective__rain__04.csv | 292,752,078 | 9275af40ae5aac61e9e5c443d39760ccf51b466ba3299bae004686921889d69a | 9275af40ae5aac61e9e5c443d39760ccf51b466ba3299bae004686921889d69a | MATCH |
| urban__good__01.csv | 295,835,938 | 4113a65cbda0ee5c0bcc371f353af95fc534dd661ea1ca29a20b8455c25e34bc | 4113a65cbda0ee5c0bcc371f353af95fc534dd661ea1ca29a20b8455c25e34bc | MATCH |
| urban__good__02.csv | 294,616,586 | 2151a0e120497352265f19bb34ba724804d7f830f6d12957b9985b63134069cd | 2151a0e120497352265f19bb34ba724804d7f830f6d12957b9985b63134069cd | MATCH |
| urban__good__03.csv | 294,920,546 | e121c53e5ddbf94e83acdf67967f8f5839e6ce6371e4b2e8396162e2a559f7c6 | e121c53e5ddbf94e83acdf67967f8f5839e6ce6371e4b2e8396162e2a559f7c6 | MATCH |
| urban__good__04.csv | 295,223,121 | 32caf815e930517657a06e47e59869e43fa5579cbaab71b83837adfc97785195 | 32caf815e930517657a06e47e59869e43fa5579cbaab71b83837adfc97785195 | MATCH |
| urban__poor__01.csv | 295,854,504 | d6c11e93d6140ee9b30f9569154b522d7064086fe793e6d68436e8c3698d5a0b | d6c11e93d6140ee9b30f9569154b522d7064086fe793e6d68436e8c3698d5a0b | MATCH |
| urban__poor__02.csv | 294,623,220 | e386854ea901283bf9a862cafcf7f1887767f932cdafb8b151775fc1dee5c0d1 | e386854ea901283bf9a862cafcf7f1887767f932cdafb8b151775fc1dee5c0d1 | MATCH |
| urban__poor__03.csv | 294,926,477 | a03931e5dbc2726e959100645a8a2b21f71692e465a90b8c8af9106482b43449 | a03931e5dbc2726e959100645a8a2b21f71692e465a90b8c8af9106482b43449 | MATCH |
| urban__poor__04.csv | 295,225,190 | 773ec7f17879224b400e61fd70395e2e80c6c4db20ebd8d2bf1abbeff10d6bda | 773ec7f17879224b400e61fd70395e2e80c6c4db20ebd8d2bf1abbeff10d6bda | MATCH |
| urban__rain__01.csv | 293,440,583 | 97bf1bfed03ffb17cd82bcfe57c188ac1f7d17dd6f9adc6cee1f3d8f2a1ca6b5 | 97bf1bfed03ffb17cd82bcfe57c188ac1f7d17dd6f9adc6cee1f3d8f2a1ca6b5 | MATCH |
| urban__rain__02.csv | 292,556,573 | 06527e5fa22037c169d509f6dc3b364149bed65f54b086c5b9a5d4c3f233873c | 06527e5fa22037c169d509f6dc3b364149bed65f54b086c5b9a5d4c3f233873c | MATCH |
| urban__rain__03.csv | 292,832,532 | 92b52218348f5fbb29da2a024695767a81c45aa1951f5c6bbe082febd75e3457 | 92b52218348f5fbb29da2a024695767a81c45aa1951f5c6bbe082febd75e3457 | MATCH |
| urban__rain__04.csv | 293,153,601 | e6ab63127ddaa2b5135e6df01c9b030aa0be070915f0711e2bd386698c4f1942 | e6ab63127ddaa2b5135e6df01c9b030aa0be070915f0711e2bd386698c4f1942 | MATCH |

The current table SHA values were independently recomputed and each matched the corresponding values in both generation_manifest.csv and qa_summary.csv. The immutable collection_manifest.json is the collection-level plan/provenance anchor; its table entries are pre-generation/planned and are not the final per-table hash source. The generated manifest and QA summary supply those final hashes.

## Decision for the approved archive operation

The formal 48-table collection and its manifest, QA, README, receipts, provenance, progress log, and released-lock record remain KEEP. This integrity gate passes, so the previously approved Darkroom archive candidates may proceed after their individual source-state and destination-collision preflight. No item inside this formal collection is an archive candidate in the current manifest.

