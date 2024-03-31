from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from math import pi, sin, radians, sqrt
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')  # Set the backend before importing pyplot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'


class PermeabilityCalculator(FlaskForm):
    # Core properties
    radius = FloatField('Core cross-sectional radius (cm)',
                        validators=[DataRequired(), NumberRange(min=0)])
    length = FloatField('Core length (cm)',
                        validators=[DataRequired(), NumberRange(min=0)])
    # Fluid properties
    angle = FloatField('Flow direction (degrees)',
                       validators=[DataRequired(),
                                   NumberRange(min=-90, max=90)])
    flowrate = FloatField('Fluid flow rate (cm^3/s)',
                          validators=[DataRequired(), NumberRange(min=0)])
    density = FloatField('Fluid density (kg/m^3)',
                         validators=[NumberRange(min=0)],
                         default=1000)  # Default value for water
    viscosity = FloatField('Fluid viscosity (Pa.s)',
                           validators=[NumberRange(min=0)],
                           default=0.001)  # Default value for water
    inlet_pressure = FloatField('Fluid inlet pressure (Pa)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    outlet_pressure = FloatField('Fluid outlet pressure (Pa)',
                                 validators=[DataRequired(),
                                             NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


class FlowUnderGravity(FlaskForm):
    # Medium properties
    permeability = FloatField('Permeability (D)',
                              validators=[DataRequired(), NumberRange(min=0)])
    # Fluid properties
    density1 = FloatField('Fluid 1 density (kg/m^3)',
                          validators=[DataRequired(), NumberRange(min=0)])
    density2 = FloatField('Fluid 2 density (kg/m^3)',
                          validators=[NumberRange(min=0)],
                          default=0)
    viscosity1 = FloatField('Fluid 1 viscosity (Pa.s)',
                            validators=[DataRequired(), NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


class Leverett(FlaskForm):
    # In the lab (L)
    interfacial_tension_L = FloatField('Interfacial tension in the lab (mN/m)',
                                       validators=[DataRequired(),
                                                   NumberRange(min=0)])
    porosity_L = FloatField('Porosity in the lab',
                            validators=[DataRequired(),
                                        NumberRange(min=0, max=1)])
    permeability_L = FloatField('Permeability in the lab (D)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    # In the field (F)
    interfacial_tension_F = \
        FloatField('Interfacial tension in the field (mN/m)',
                   validators=[DataRequired(), NumberRange(min=0)])
    porosity_F = FloatField('Porosity in the field',
                            validators=[DataRequired(),
                                        NumberRange(min=0, max=1)])
    permeability_F = FloatField('Permeability in the field (D)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/permeability', methods=['GET', 'POST'])
def calculate_permeability():
    calculator = PermeabilityCalculator()
    permeability = None
    if calculator.validate_on_submit():
        radius = calculator.radius.data / 100  # Convert to m
        length = calculator.length.data / 100  # Convert to m
        angle = radians(calculator.angle.data)  # Convert to radians
        flowrate = calculator.flowrate.data / 10**6  # Convert to m^3/s
        density = calculator.density.data
        viscosity = calculator.viscosity.data
        inlet_pressure = calculator.inlet_pressure.data
        outlet_pressure = calculator.outlet_pressure.data
        # Calculate permeability
        darcy_velocity = flowrate / (pi * radius**2)
        gravity = 9.81 * sin(angle)
        pressure_gradient = (inlet_pressure - outlet_pressure) / length
        permeability = (darcy_velocity * viscosity) / \
            (pressure_gradient + (density * gravity)) * 10**12  # in Darcy

    else:
        print(calculator.errors)

    return render_template('permeability.html',
                           form=calculator,
                           permeability=permeability)


@app.route('/flow-under-gravity', methods=['GET', 'POST'])
def flow_under_g():
    calculator = FlowUnderGravity()
    darcy_velocity = None
    if calculator.validate_on_submit():
        permeability = calculator.permeability.data
        density1 = calculator.density1.data
        density2 = calculator.density2.data
        viscosity1 = calculator.viscosity1.data
        # Calculate hydraulic conductivity (1-phase)
        # or Darcy velocity (2-phase)
        darcy_velocity = \
            abs(permeability / viscosity1 * (density1 - density2) * 9.81)
        darcy_velocity *= 10**-12

    else:
        print(calculator.errors)

    return render_template('flow_under_g.html',
                           form=calculator,
                           darcy_velocity=darcy_velocity)


@app.route('/leverett', methods=['GET', 'POST'])
def leverett():
    calculator = Leverett()
    saturations, capillary_pressures_L, capillary_pressures_F = [], [], []
    if calculator.validate_on_submit():
        interfacial_tension_L = calculator.interfacial_tension_L.data
        porosity_L = calculator.porosity_L.data
        permeability_L = calculator.permeability_L.data
        S_and_Pc_lab = {}

        # Get the capillary pressure in the lab and saturation values
        i = 1
        while True:
            Pc_lab_name = f'capillary_pressure_L_{i}'
            S_name = f'saturation_{i}'

            if Pc_lab_name in request.form and S_name in request.form:
                Pc_lab = float(request.form[Pc_lab_name])
                S = float(request.form[S_name])
                S_and_Pc_lab[S] = Pc_lab
                i += 1
            else:
                break
        S_and_Pc_lab = dict(sorted(S_and_Pc_lab.items()))
        saturations = list(S_and_Pc_lab.keys())
        capillary_pressures_L = list(S_and_Pc_lab.values())

        interfacial_tension_F = calculator.interfacial_tension_F.data
        porosity_F = calculator.porosity_F.data
        permeability_F = calculator.permeability_F.data

        # Calculate the proportional constant A (Pc_field = A * Pc_lab)
        interfacial_tension_ratio = \
            interfacial_tension_F / interfacial_tension_L
        porosity_ratio = porosity_F / porosity_L
        permeability_ratio = permeability_F / permeability_L
        A = interfacial_tension_ratio * \
            sqrt(porosity_ratio / permeability_ratio)

        # Calculate capillary pressures in the field
        for Pc_lab in capillary_pressures_L:
            capillary_pressures_F.append(A * Pc_lab)

    else:
        print(calculator.errors)

    if capillary_pressures_F:
        plt.plot([min(saturations), max(saturations)], [0, 0], '--', c='gray')
        plt.plot(saturations, capillary_pressures_L, label='Lab', marker='.')
        plt.plot(saturations, capillary_pressures_F, label='Field', marker='.')
        plt.xlabel('Saturation')
        plt.ylabel('Capillary pressure (Pa)')
        plt.legend()
        plt.savefig('static/leverett.png')
        plt.close()

    return render_template(
        'leverett.html',
        form=calculator,
        saturations=saturations,
        capillary_pressures_L=capillary_pressures_L,
        capillary_pressures_F=capillary_pressures_F,
    )


if __name__ == '__main__':
    app.run(debug=True)  # Add debug=True to run the app in debug mode
