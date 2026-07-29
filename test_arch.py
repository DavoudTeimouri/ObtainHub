import sys
import importlib

for mod in list(sys.modules.keys()):
    if 'obtainhub' in mod:
        del sys.modules[mod]

sys.path.insert(0, '/root/project/github/public-repository/ObtainHub')
from obtainhub.core.asset_matcher import AssetMatcher, Architecture

matcher = AssetMatcher()
print('Architecture.X64:', Architecture.X64)
print('arch_regexes keys:', list(matcher.arch_regexes.keys()))
print()

# Test the loop
name = 'app-x64.msi'
print('Testing:', name)
for arch in [Architecture.X64, Architecture.ARM64, Architecture.X86]:
    print('  Checking:', arch)
    for regex in matcher.arch_regexes[arch]:
        result = regex.search(name)
        if result:
            print('    MATCH:', regex.pattern, '->', result.group())
            break
    else:
        print('    No match for', arch)