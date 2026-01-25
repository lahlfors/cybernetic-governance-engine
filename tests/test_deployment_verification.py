import os
import unittest

import yaml


class TestDeploymentConfig(unittest.TestCase):

    def test_service_yaml_structure(self):
        """Validates that service.yaml has the correct sidecar structure."""
        with open("deployment/service.yaml") as f:
            config = yaml.safe_load(f)

        containers = config['spec']['template']['spec']['containers']

        # Check for 2 containers (Agent + Sidecar)
        self.assertEqual(len(containers), 2)

        agent = next(c for c in containers if c['name'] == 'ingress-agent')
        sidecar = next(c for c in containers if c['name'] == 'governance-sidecar')

        # Check OPA Image Pinned
        self.assertTrue(sidecar['image'].startswith("openpolicyagent/opa:0.68.0-static"))

        # Check Mounts
        volume_mounts = [m['name'] for m in sidecar['volumeMounts']]
        self.assertIn('policy-volume', volume_mounts)
        self.assertIn('auth-token-vol', volume_mounts)

    def test_deploy_script_paths(self):
        """Verifies that the paths referenced in deploy_all.py exist."""
        # This is a static check of the expectations
        self.assertTrue(os.path.exists("deployment/system_authz.rego"))
        self.assertTrue(os.path.exists("deployment/opa_config.yaml"))
        self.assertTrue(os.path.exists("src/governance/policy/finance_policy.rego"))
        self.assertTrue(os.path.exists("deployment/service.yaml"))

if __name__ == '__main__':
    unittest.main()
