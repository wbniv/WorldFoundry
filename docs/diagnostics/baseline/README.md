# Baseline verification evidence

[Default desktop session](default/README.md) passes source/compiled and native gameplay checks. Its packaged APK and native-library hashes are recorded in the receipt.

[Diagnostics receipt](diagnostics/build-receipt.json) and [checks](diagnostics/verification.json) verify export and compilation of the optional fixtures. [Settings-gallery receipt](settings-gallery/build-receipt.json) and [checks](settings-gallery/verification.json) verify its 118-field OAS/OAD source fixture and two attached owner catalogs. These optional runs do not certify slope traversal or interactive settings behavior.

[Shared generic settings acceptance](generic-settings/README.md) records passing
default/gallery checks on both Chromecasts and main CD integration at index 7.
The shared host and plant consumer migration were explicitly authorized and
implemented. Plant device acceptance also passed on both Chromecasts, including native
text entry, regeneration, held/released input and lifecycle/exit checks.
