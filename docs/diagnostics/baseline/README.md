# Baseline verification evidence

[Default desktop session](default/README.md) passes source/compiled and native gameplay checks. Its packaged APK and native-library hashes are recorded in the receipt.

[Diagnostics receipt](diagnostics/build-receipt.json) and [checks](diagnostics/verification.json) verify export and compilation of the optional fixtures. [Settings-gallery receipt](settings-gallery/build-receipt.json) and [checks](settings-gallery/verification.json) verify its 118-field OAS/OAD source fixture and two attached owner catalogs. These optional runs do not certify slope traversal or interactive settings behavior.

Chromecast acceptance awaits baseline registration in the shared coordinator. Generic editor selection awaits the explicit engine approval described in the [proposal](../../../wflevels/baseline/docs/generic-settings-integration.md). Main CD integration is gated on matching native/device acceptance.
