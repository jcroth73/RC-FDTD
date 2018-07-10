import numpy as np
from tqdm import tqdm
"""
Contains the classes used to represent a simulation
"""

class Sim:
    """Represents a single simulation. Field is initialized to all zeros.

    :param i0: The spatial value at which the field starts
    :param i1: The spatial value at which the field ends
    :param di: The spatial step size
    :param n0: The temporal value at which the field starts
    :param n1: The temporal value at which the field ends
    :param dn: The temporal step size
    :param store: The fraction of temporal steps to store (any value between 0 (0%) and 1 (100%)), defaults to 1 (i.e. 100%)
    :param cfield: The current field
    :param boundary: The boundary type of the field, either 'zero', for fields bounded by zeros, 'periodic' for periodic boundary conditions, or 'mirror' for boundaries that reflect inner field values.
    :param vacuum_permittivity: :math:`\epsilon_0`
    :param infinity_permittivity: :math:`\epsilon_\infty`
    :param vacuum_permeability: :math:`\mu_0`
    :param susceptibility: A susceptibility object
    :param initial_susceptibility: The initial susceptability. Eventually will be included in the susceptibility object.
    :param current_field: A field object that represents the current
    :param dtype: The data type to store the field values in
    """

    # Define constants
    CHI_A = 0
    CHI_B = 1
    CHI_GAMMA = 2
    CHI_BETA = 3
    
    def __init__(self, i0, i1, di, n0, n1, dn, store, cfield, boundary, vacuum_permittivity, infinity_permittivity, vacuum_permeability, susceptibility, initial_susceptibility, dtype=np.float):
        # Save storage amount and data type
        self._store = store
        self._dtype = dtype
        # Check that arguments have acceptable values
        if i0 > i1:
            raise ValueError("i0 must be less than or equal to i1.")
        elif n0 > n1:
            raise ValueError("n0 must be less than or equal to n1.")
        elif di <= 0:
            raise ValueError("di must be greater than zero.")
        elif dn <= 0:
            raise ValueError("dn must be greater than zero.")
        elif type(cfield) is not np.ndarray:
            raise TypeError("cfield must be of type Field.")
        # Determine the number of temporal and spatial cells in the field
        self._nlen, self._ilen = Sim.calc_dims(n0, n1, dn, i0, i1, di)
        # Determine how often to save the field
        self._n_step_btwn_store = int(1/store)
        self._nlen_save = int(np.floor(self._nlen/self._n_step_btwn_store))
        # Raise further errors
        if (self._nlen, self._ilen) != np.shape(cfield):
            raise ValueError("Expected cfield to have dimensions " + str(self.get_dims()) + " but found " + str(np.shape(cfield)) + " instead")
        elif (4, self._ilen) != np.shape(susceptibility)[0:2] or 1 > np.shape(susceptibility)[2]:
            raise ValueError("Expected dimensions of susceptability to be (4, " + str(self._ilen) + ", ?) (where ? is any positive non-zero integer) but found " + str(np.shape(susceptibility)) + " instead")
        # Save field dimensions and resolution
        self._i0 = i0
        self._i1 = i1
        self._di = di
        self._n0 = n0
        self._n1 = n1
        self._dn = dn
        # Save chi info
        self._chi = susceptibility
        self._jlen = np.shape(self._chi)[2]
        #self._calc_dchi()
        # TODO Automatically calculate chi0
        self._chi0 = initial_susceptibility
        # Save boundary condition
        self._bound = boundary
        # Create each field
        self._efield = np.zeros(self._ilen, dtype=self._dtype)
        self._hfield = np.zeros(self._ilen, dtype=self._dtype)
        # Create the save fields
        self._efield_save = np.zeros((self._nlen_save, self._ilen), dtype=self._dtype)
        self._hfield_save = np.zeros((self._nlen_save, self._ilen), dtype=self._dtype)
        # Save the current field
        self._cfield = cfield
        # Save constants
        self._epsilon0 = vacuum_permittivity
        self._epsiloninf = infinity_permittivity
        self._mu0 = vacuum_permeability
        # Calculate simulation proportionality constants
        self._coeffe0 = self._epsiloninf/(self._epsiloninf + self._chi0)
        self._coeffe1 = 1.0/(self._epsiloninf + self._chi0)
        self._coeffe2 = self._dn/(self._epsilon0 * self._di * (self._epsiloninf + self._chi0))
        self._coeffe3 = self._dn/(self._epsilon0 * (self._epsiloninf + self._chi0))
        self._coeffh1 = self._dn/(self._mu0 * self._di)
        # Calculate dchi


    def __str__(self):
        """
        Returns a descriptive string of the Sim object.
        """
        to_return = ''
        to_return += '----------\nConstants:\n'
        to_return += 'epsilon0:' + '{0:.3f}'.format(self._epsilon0) + ' epsiloninf:' + '{0:.3f}'.format(self._epsiloninf) + ' mu0:' + '{0:.3f}'.format(self._mu0) + ' chi:' + 'NOT YET IMPLEMENTED' + ' chi0:' + '{0:.3f}'.format(self._chi0)
        to_return += '\n-------------\nCoefficients:\n'
        to_return += 'e1:' + '{0:.3f}'.format(self._coeffe0) + ' e2:' + '{0:.3f}'.format(self._coeffe1) + ' e3:' + '{0:.3f}'.format(self._coeffe2) + ' e4:' + '{0:.3f}'.format(self._coeffe3) + ' h2:' + '{0:.3f}'.format(self._coeffh1)
        to_return += '\n-------\nBounds:\n'
        to_return += 'i0:' + '{0:.3f}'.format(self._i0) + ' i1:' + '{0:.3f}'.format(self._i1) + ' di:' + '{0:.3f}'.format(self._di) + '\nn0:' + '{0:.3f}'.format(self._n0) + ' n1:' + '{0:.3f}'.format(self._n1) + ' dn:' + '{0:.3f}'.format(self._dn)
        to_return += '\n-------\nDimensions:\n'
        to_return += '( n x i ): ( ' + str(self._nlen) + ' x ' + str(self._ilen) + ' )'
        return to_return
        
    def simulate(self):
        """
        Executes the simulation.
        """
        n_save = 0
        # Simulate for one less step than the number of temporal indicies because initializing the fields to zero takes up the first temporal index
        for n in tqdm(range(self._nlen), desc='Executing simulation'):
            # Calculate the H and E fields
            if self._bound == 'zero': # Zero boundary condition
                self._zero(n)
            if self._bound == 'absorbing': # Absorbing boundary condition
                self._absorbing(n)
            # Save the new fields if at an appropriate step
            if n % self._n_step_btwn_store == 0:
                self._hfield_save[n_save] = self._hfield
                self._efield_save[n_save] = self._efield
                n_save += 1

    def _absorbing(self, n):
        """
        Computes the E-field and H-fields at time step n with constant zero boundaries.
        """
        pass

    def _zero(self, n):
        """
        Computes the E-field and H-fields at time step n with constant zero boundaries.
        """
        # Compute H-field and update
        h_t1 = self._hfield[:-1]
        h_t2 = self._coeffh1 * (self._efield[1:]-self._efield[:-1])
        self._hfield[:-1] = h_t1 - h_t2
        # Compute E-field and update
        e_t1 = self._coeffe0 * self._efield[1:]
        e_t2 = self._coeffe1 * self._calc_psi(n)
        e_t3 = self._coeffe2 * (self._hfield[1:]-self._hfield[:-1])
        e_t4 = self._coeffe3 * self._cfield[n,1:]
        self._efield[1:] = e_t1 + e_t2 - e_t3 - e_t4
        
    def _calc_psi(self, n):
        """
        Returns psi

        :return: Zero
        """
        return 0

    def _calc_dchi(self):
        # Create an array to store the dchi values in
        self._dchi = np.zeros((self._nlen, self._ilen), dtype=self._dtype)
        for m in tqdm(range(self._nlen), desc='Calculating dchi'):
            # Set dchi at the current m value to zero because no summing has occured yet
            self._dchi[m] = 0
            for j in range(self._jlen):
                # Save constants to make things easier
                A = self._chi[self.CHI_A,:,j]
                B = self._chi[self.CHI_B,:,j]
                gamma = self._chi[self.CHI_GAMMA,:,j]
                beta = self._chi[self.CHI_BETA,:,j]
                dt = self._dn
                # Calculate dchi at M value
                self._dchi[m] += (A/(beta-gamma)) * ( 2*np.exp((-gamma+beta)*dt) - 1 - np.exp(2*(-gamma+beta)*dt) ) * np.exp((-gamma+beta)*m*dt)
                self._dchi[m] += (B/(-beta-gamma)) * ( 2*np.exp((-gamma-beta)*dt) - 1 - np.exp(2*(-gamma-beta)*dt) ) * np.exp((-gamma-beta)*m*dt)



    def get_bound_res(self):
        """
        Returns the boundaries and resolution of the simulation.

        :return: A tuple :code:`(n0, n1, dn, i0, i1, di)`
        """
        return (self._n0, self._n1, self._dn, self._i0, self._i1, self._di)

    def get_dims(self):
        """
        Returns the dimensions of the field in cells.

        :returns: A tuple :code:`(nlen, ilen)` containing the temporal and spatial dimensions in cells
        """
        return (self._nlen, self._ilen)

    def export(self):
        """
        Exports all field values along with the spatial and temporal bounds of each field cell

        :return: A tuple :code:`(n, i, e, h, c)` where :code:`n` is a Numpy array containing the spatial bounds of each field cell, :code:`i` is a Numpy array containing the temporal bounds of each field cell, :code:`e` is a Numpy array containing the E-field (axis=0 is time and axis=1 is space), :code:`h` is a Numpy array containing the H-field (axis=0 is time and axis=1 is space), and :code:`c` is a Numpy array containing the current field (axis=0 is time and axis=1 is space)
        """
        # Calcualte the n and i arrays
        n = np.linspace(self._n0, self._n1, self._nlen_save, False)
        i = np.linspace(self._i0, self._i1, self._ilen, False)
        # Return
        return (n, i, self._efield_save, self._hfield_save, self._cfield)
        
    @staticmethod
    def calc_dims(n0, n1, dn, i0, i1, di):
        """
        Calculates the dimensions of the simulation in cells.

        :param i0: The spatial value at which the field starts
        :param i1: The spatial value at which the field ends
        :param di: The spatial step size
        :param n0: The temporal value at which the field starts
        :param n1: The temporal value at which the field ends
        :param dn: The temporal step size
        :return: A tuple (nlen, ilen) of the temporal and spatial dimensions
        """
        nlen = int(np.floor((n1-n0)/dn))
        ilen = int(np.floor((i1-i0)/di)+2) # Add two to account for boundary conditions
        return (nlen, ilen)