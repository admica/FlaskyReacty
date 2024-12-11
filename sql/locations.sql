-- SQL insert for almost all space centers and facilities:

BEGIN;
INSERT INTO locations (site, name, latitude, longitude, description) VALUES
-- Original NASA Centers
('HQ', 'NASA Headquarters', 38.882987, -77.016231, 'Washington, DC headquarters'),
('JSC', 'Johnson Space Center', 29.559653, -95.09273, 'Human spaceflight center in Houston, TX'),
('KSC', 'Kennedy Space Center', 28.585536, -80.649204, 'Primary launch facility in FL'),
('MSFC', 'Marshall Space Flight Center', 34.631046, -86.674085, 'Propulsion and space systems in Huntsville, AL'),
('GSFC', 'Goddard Space Flight Center', 38.998439, -76.852608, 'Earth and space science in Greenbelt, MD'),
('ARC', 'Ames Research Center', 37.41187, -122.062855, 'Aeronautics and exploration tech in Mountain View, CA'),
('JPL', 'Jet Propulsion Laboratory', 34.201232, -118.17435, 'Robotic space exploration in Pasadena, CA'),
('GRC', 'Glenn Research Center', 41.412726, -81.862127, 'Aerospace and propulsion research in Cleveland, OH'),
('LaRC', 'Langley Research Center', 37.09324, -76.382124, 'Aviation research in Hampton, VA'),
('SSC', 'Stennis Space Center', 30.39183, -89.640086, 'Rocket engine testing in MS'),
('WFF', 'Wallops Flight Facility', 37.940199, -75.466498, 'Launch site in VA'),
('WSTF', 'White Sands Test Facility', 32.50109, -106.971741, 'Testing facility in NM'),
('AFRC', 'Armstrong Flight Research Center', 34.954265, -117.883737, 'Aeronautical research in Edwards, CA'),

-- NASA International Facilities
('MGS', 'McMurdo Ground Station', -77.838836, 166.654022, 'NASA ground station in Antarctica'),
('CDSCC', 'Canberra Deep Space Communication Complex', -35.401389, 148.981667, 'NASA deep space network facility in Australia'),
('MDSCC', 'Madrid Deep Space Communications Complex', 40.431389, -4.251111, 'NASA deep space network facility in Spain'),
('GDSCC', 'Goldstone Deep Space Communications Complex', 35.426667, -116.89, 'NASA deep space network facility in California'),
('ASF', 'Alaska Satellite Facility', 64.859722, -147.850833, 'NASA research facility in Fairbanks'),
('ESRANGE', 'Esrange Space Center', 67.893889, 21.066944, 'NASA partner facility in Sweden'),
('SANSA', 'South African National Space Agency', -25.887778, 27.707778, 'NASA partner facility in South Africa'),
('CONAE', 'Argentine Space Agency', -31.528889, -68.465278, 'NASA partner facility in Argentina'),

-- JAXA
('JAXA-T', 'JAXA Tsukuba Space Center', 36.066111, 140.130833, 'JAXA main R&D center in Tsukuba, Japan'),
('JAXA-TN', 'JAXA Tanegashima Space Center', 30.400556, 130.975278, 'JAXA primary launch site'),
('JAXA-U', 'JAXA Uchinoura Space Center', 31.251944, 131.082778, 'JAXA sounding rocket and small satellites launch site'),

-- ESA
('ESA-EAC', 'European Astronaut Centre', 50.912814, 7.005647, 'ESA astronaut training in Cologne, Germany'),
('ESA-ESTEC', 'European Space Research and Technology Centre', 52.218374, 4.419639, 'ESA technical center in Netherlands'),
('ESA-ESOC', 'European Space Operations Centre', 49.871444, 8.622781, 'ESA mission control in Darmstadt, Germany'),
('ESA-ESRIN', 'European Space Research Institute', 41.827778, 12.674167, 'ESA Earth observation center in Italy'),
('ESA-CSG', 'Guiana Space Center', 5.237222, -52.768333, 'ESA primary launch site in French Guiana'),

-- Roscosmos
('ROSCOSMOS', 'Baikonur Cosmodrome', 45.965, 63.305, 'Primary Russian launch facility in Kazakhstan'),
('VOSTOCHNY', 'Vostochny Cosmodrome', 51.884395, 128.333932, 'New Russian launch facility in Amur Oblast'),
('PLESETSK', 'Plesetsk Cosmodrome', 62.925556, 40.577778, 'Russian military space facility'),

-- ISRO
('ISRO-SHAR', 'Satish Dhawan Space Centre', 13.733333, 80.235278, 'Indian primary launch site'),
('ISRO-VSSC', 'Vikram Sarabhai Space Centre', 8.5288, 76.868743, 'Indian space research center'),

-- China
('JSLC', 'Jiuquan Satellite Launch Center', 40.958333, 100.291667, 'Chinese launch site for crewed missions'),
('XSLC', 'Xichang Satellite Launch Center', 28.246017, 102.026556, 'Chinese launch site for geosynchronous orbit'),
('WSLC', 'Wenchang Spacecraft Launch Site', 19.614492, 110.951133, 'Chinese newest launch site'),
('TSLC', 'Taiyuan Satellite Launch Center', 38.849086, 111.608497, 'Chinese polar orbit launch site'),

-- Others
('NARO', 'Naro Space Center', 34.431944, 127.535, 'South Korean space center'),
('ALCANTARA', 'Alcântara Launch Center', -2.373056, -44.396389, 'Brazilian launch site'),

-- Additional High-Confidence Sites
('ALMA', 'Atacama Large Millimeter Array', -23.029278, -67.754911, 'Radio telescope array in Chile with NASA partnership'),
('OCTL', 'Optical Communications Telescope Lab', 35.210833, -111.641944, 'NASA optical communications research in Arizona'),
('NRAO', 'National Radio Astronomy Observatory', 38.433056, -79.839722, 'Radio astronomy facility in Green Bank, WV'),
('NOAA-FB', 'NOAA Satellite Operations Facility', 38.992500, -76.852500, 'Satellite control center in Suitland, MD'),
('PSCA', 'Pacific Spaceport Complex Alaska', 57.435833, -152.337778, 'Commercial launch site in Kodiak, Alaska'),
('MARS', 'Mid-Atlantic Regional Spaceport', 37.843333, -75.478333, 'Commercial launch site at Wallops'),
('VAFB', 'Vandenberg Air Force Base', 34.750000, -120.500000, 'Military and NASA launch site in California'),
('KWAJ-RTS', 'Kwajalein Missile Range', 8.716667, 167.733333, 'US missile range and space tracking'),
('SVALBARD', 'Svalbard Satellite Station', 78.229772, 15.407786, 'Polar orbit ground station in Norway'),
('TROLL', 'Troll Satellite Station', -72.011389, 2.538333, 'Antarctic research and ground station'),
('DONGARA', 'Dongara Ground Station', -29.045556, 115.350833, 'Australian space tracking facility'),
('REDU', 'ESA Redu Centre', 50.001667, 5.146667, 'ESA control center in Belgium'),
('KIRUNA', 'Esrange Satellite Station', 67.893889, 21.066944, 'Swedish space communications facility'),
('RAAF-WOO', 'Woomera Test Range', -30.958333, 136.541667, 'Australian launch facility'),
('SVOM', 'Space Variable Objects Monitor', 28.208333, 102.033333, 'China-France gamma-ray observatory'),
('EISCAT', 'European Incoherent Scatter Scientific Association', 69.585556, 19.227778, 'Space research facility in Norway'),
('SOHAE', 'Sohae Satellite Launching Station', 39.660000, 124.705000, 'North Korean launch facility'),
('IMAM', 'Imam Khomeini Space Center', 35.234722, 53.920833, 'Iranian space launch center');
COMMIT;
