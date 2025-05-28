local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  // Project-specific
  description: 'Save Patreon content you have access to.',
  keywords: ['command line', 'patreon'],
  project_name: 'patreon-archiver',
  version: '0.1.3',
  want_main: true,
  supported_python_versions: ['3.%d' % i for i in std.range(12, 13)],
  citation+: {
    'date-released': '2025-05-28',
  },
  pyproject+: {
    project+: {
      scripts: {
        'patreon-archiver': 'patreon_archiver.main:main',
      },
    },
    tool+: {
      poetry+: {
        dependencies+: {
          requests: '^2.32.3',
          'yt-dlp-utils': '^0.0.4',
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-requests': '^2.32.0.20250515',
              'yt-dlp-types': '^0',
            },
          },
        },
      },
    },
  },
  // Common
  authors: [
    {
      'family-names': 'Udvare',
      'given-names': 'Andrew',
      email: 'audvare@gmail.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  local funding_name = '%s2' % std.asciiLower(self.github_username),
  github_username: 'Tatsh',
  github+: {
    funding+: {
      ko_fi: funding_name,
      liberapay: funding_name,
      patreon: funding_name,
    },
  },
}
