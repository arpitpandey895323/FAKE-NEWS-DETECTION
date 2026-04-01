import unittest

class TestBoundaryValueAnalysis(unittest.TestCase):
    def test_boundary_values(self):
        # Assuming a function called `is_valid_input` to be tested
        self.assertTrue(is_valid_input(0))   # Lower boundary
        self.assertTrue(is_valid_input(1))   # Just above lower boundary
        self.assertTrue(is_valid_input(100)) # Just below upper boundary
        self.assertFalse(is_valid_input(101))# Above upper boundary


class TestEquivalencePartitioning(unittest.TestCase):
    def test_equivalence_partitions(self):
        # Assuming a function `get_user_role`
        self.assertEqual(get_user_role('admin'), 'Administrator')
        self.assertEqual(get_user_role('user'), 'Regular User')
        self.assertEqual(get_user_role('guest'), 'Guest User')
        self.assertNotEqual(get_user_role('admin'), 'Regular User')


if __name__ == '__main__':
    unittest.main()