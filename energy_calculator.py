class PianoEnergyCalculator:
    """Calculate physical energy for Numa X Piano key presses"""
    
    def __init__(self):
        # Numa X Piano specifications (from research)
        self.ACTUATION_FORCE = 0.574  # Newtons (58.5 grams-force)
        self.KEY_TRAVEL = 0.01  # meters (10mm)
    
    def calculate_note_energy(self, velocity):
        """Calculate energy in Joules for a single note press"""
        velocity_factor = 1 + (velocity / 127)
        energy = self.ACTUATION_FORCE * self.KEY_TRAVEL * velocity_factor
        return energy
    
    def format_energy(self, joules):
        """Format energy for display"""
        if joules < 0.001:
            return f"{joules * 1000000:.1f} µJ"
        elif joules < 1:
            return f"{joules * 1000:.2f} mJ"
        else:
            return f"{joules:.3f} J"